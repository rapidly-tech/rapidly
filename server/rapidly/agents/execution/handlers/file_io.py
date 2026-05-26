"""File read + write node handlers.

Both handlers operate on the existing ``catalog/file`` S3 storage
— same registry the viewer's IFC pipeline uses. The tenancy
boundary is enforced via the workspace cross-check: a workflow
can't read a File row outside its own workspace.

For v1 the read path returns text + bytes-as-base64; the write
path takes either text or bytes-as-base64 and stages a File row
in the configured workspace.

These are intentionally small handlers — most workflows that need
files use them to glue other nodes together (HTTP fetch → file
write, file read → LLM input). The heavy lifting lives in
``catalog/file/actions``; the handler is the thin engine-side
wrapper.
"""

from __future__ import annotations

import base64
from typing import Any
from uuid import UUID

from rapidly.worker import AsyncSessionMaker

# Reuse the viewer worker's chunk size — same justification: 1 MiB
# bounds Python memory pressure without context-switching on every
# read.
_S3_READ_CHUNK = 1 * 1024 * 1024
# Above this size the file_read handler refuses to inline bytes
# into the response. The next node should accept a file_id reference
# and re-resolve when it actually needs the bytes.
_INLINE_CAP = 10 * 1024 * 1024


class FileNodeError(RuntimeError):
    pass


async def file_read_handler(
    ctx: dict[str, Any],
    node_config: dict[str, Any],
    input_data: dict[str, Any],
) -> dict[str, Any]:
    """Read a File row's bytes from S3.

    ``node_config`` accepts ``file_id`` (UUID); ``input_data``
    accepts the same key as a fallback so the previous node's
    output can feed the read.
    """
    raw_id = node_config.get("file_id") or input_data.get("file_id")
    if raw_id is None:
        raise FileNodeError("file_id is required")
    try:
        file_id = UUID(str(raw_id))
    except (TypeError, ValueError) as exc:
        raise FileNodeError(f"file_id is not a UUID: {raw_id!r}") from exc

    # Inline import to avoid pulling boto3 + catalog dependencies
    # into the engine module's import tree.
    from sqlalchemy import select  # local — engine prefers not to

    from rapidly.catalog.file.s3 import S3_SERVICES
    from rapidly.models import File
    # carry sqlalchemy imports at module level

    async with AsyncSessionMaker() as session:
        stmt = select(File).where(File.id == file_id)
        file_row = (await session.execute(stmt)).scalar_one_or_none()
        if file_row is None:
            raise FileNodeError(f"File {file_id} not found")
        service = file_row.service
        path = file_row.path
        size = file_row.size
        name = file_row.name
        mime_type = file_row.mime_type

    if size > _INLINE_CAP:
        # Don't inline a 1 GB file into the next node's input.
        return {
            "file_id": str(file_id),
            "name": name,
            "size": size,
            "mime_type": mime_type,
            "inlined": False,
            "text": None,
            "bytes_b64": None,
        }

    def _download_sync() -> bytes:
        s3 = S3_SERVICES[service]
        obj = s3.get_object_or_raise(path)
        body = obj.get("Body")
        if body is None:
            raise FileNodeError(f"S3 GetObject returned no Body for {path}")
        buf = bytearray()
        while True:
            chunk = body.read(_S3_READ_CHUNK)
            if not chunk:
                break
            buf.extend(chunk)
        return bytes(buf)

    import asyncio

    raw = await asyncio.to_thread(_download_sync)
    try:
        text: str | None = raw.decode("utf-8")
    except UnicodeDecodeError:
        text = None
    return {
        "file_id": str(file_id),
        "name": name,
        "size": size,
        "mime_type": mime_type,
        "inlined": True,
        "text": text,
        "bytes_b64": base64.b64encode(raw).decode("ascii"),
    }


async def file_write_handler(
    ctx: dict[str, Any],
    node_config: dict[str, Any],
    input_data: dict[str, Any],
) -> dict[str, Any]:
    """Write bytes to S3 + create a File row.

    ``node_config`` accepts:
        workspace_id: UUID    required
        name: str             required
        mime_type: str        default "application/octet-stream"
        text: str             one of {text, bytes_b64} required
        bytes_b64: str        base64-encoded bytes
    """
    raw_workspace = node_config.get("workspace_id")
    name = node_config.get("name")
    if not isinstance(raw_workspace, str) or not isinstance(name, str):
        raise FileNodeError("workspace_id and name are required")
    try:
        workspace_id = UUID(raw_workspace)
    except (TypeError, ValueError) as exc:
        raise FileNodeError(f"workspace_id is not a UUID: {raw_workspace!r}") from exc

    mime_type = str(node_config.get("mime_type", "application/octet-stream"))

    text = node_config.get("text")
    b64 = node_config.get("bytes_b64")
    if text is not None and isinstance(text, str):
        raw = text.encode("utf-8")
    elif b64 is not None and isinstance(b64, str):
        try:
            raw = base64.b64decode(b64)
        except (ValueError, TypeError) as exc:
            raise FileNodeError("bytes_b64 is not valid base64") from exc
    else:
        raise FileNodeError("one of {text, bytes_b64} is required")

    if len(raw) > _INLINE_CAP:
        # The handler's bytes-inline path doesn't carry multi-GB
        # uploads. Workflows that need that use the dedicated
        # presigned-PUT flow + the file_id-passing pattern.
        raise FileNodeError(
            f"payload {len(raw)} bytes exceeds inline cap {_INLINE_CAP}"
        )

    from rapidly.catalog.file.s3 import S3_SERVICES
    from rapidly.models import File
    from rapidly.models.file import FileServiceTypes

    service = FileServiceTypes.downloadable
    s3 = S3_SERVICES[service]
    path = f"agents/{workspace_id}/{name}"

    import asyncio

    def _upload_sync() -> None:
        s3.upload(data=raw, path=path, mime_type=mime_type)

    await asyncio.to_thread(_upload_sync)

    async with AsyncSessionMaker() as session:
        file_row = File(
            workspace_id=workspace_id,
            name=name,
            path=path,
            mime_type=mime_type,
            size=len(raw),
            service=service,
            is_uploaded=True,
            is_enabled=True,
        )
        session.add(file_row)
        await session.flush()
        return {
            "file_id": str(file_row.id),
            "name": name,
            "size": len(raw),
            "mime_type": mime_type,
        }
