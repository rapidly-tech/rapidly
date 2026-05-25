"""Dramatiq actor that parses an uploaded IFC into XKT.

The IfcOpenShell + xeokit toolchain ships as system binaries (apt:
``ifcopenshell-tools``, vendored ``IfcConvert`` CLI). We subprocess
out to ``IfcConvert`` rather than import IfcOpenShell into the
Python process for three reasons:

1. IFC parsing is memory-hungry; a subprocess gets its own address
   space so an OOM kills the worker, not the API.
2. Decoupling from the Python ABI means we can upgrade the parser
   without restarting Python workers.
3. The xeokit ``IfcConvert`` CLI emits XKT directly, which is what
   the frontend viewer loads — no in-Python translation layer
   needed.

Lifecycle this actor enforces:
    uploaded -> parsing -> ready  (happy path)
    uploaded -> parsing -> failed (any subprocess error, with
                                    error_message populated)

Session-flush discipline: this actor uses ``session.flush()`` only.
The Dramatiq actor framework persists at task completion; explicit
session-level transaction control would race with that.
"""

from __future__ import annotations

import asyncio
import json
import shutil
import subprocess
import tempfile
from pathlib import Path
from uuid import UUID

import structlog
from sqlalchemy import select

from rapidly.models import FederatedModel, ModelDiscipline, ModelStatus
from rapidly.worker import AsyncSessionMaker, TaskPriority, actor

_log = structlog.get_logger(__name__)


# Subprocess timeout. Parsing a 250 MB IFC takes ~5 min on the
# 4 GB worker; capping at 30 min covers larger fixtures while still
# protecting the worker from a runaway parse.
_PARSE_TIMEOUT_S = 30 * 60

# Maximum bytes we'll read from a single XKT file before refusing
# to upload. Defence against a runaway parse producing a multi-GB
# output that would blow MinIO + the frontend.
_MAX_XKT_BYTES = 2 * 1024 * 1024 * 1024  # 2 GB


@actor(actor_name="viewer.parse_ifc", priority=TaskPriority.LOW, max_retries=2)
async def parse_ifc(model_id: UUID) -> None:
    """Parse the IFC backing ``model_id`` and produce the XKT."""
    async with AsyncSessionMaker() as session:
        model = await _load_model(session, model_id)
        if model is None:
            _log.warning("viewer.parse_ifc.model_missing", model_id=str(model_id))
            return

        if model.status not in (ModelStatus.uploaded, ModelStatus.failed):
            # Idempotent: a second dispatch (retry, manual re-trigger)
            # of an already-parsing or already-ready row is a no-op.
            _log.info(
                "viewer.parse_ifc.skip", model_id=str(model_id), status=model.status
            )
            return

        model.status = ModelStatus.parsing
        await session.flush()

    # Parsing happens outside the session so a long subprocess
    # doesn't hold a DB connection. State writes re-open a session.
    try:
        result = await _run_ifc_convert(model_id)
    except Exception as exc:
        _log.exception("viewer.parse_ifc.failed", model_id=str(model_id))
        async with AsyncSessionMaker() as session:
            model = await _load_model(session, model_id)
            if model is not None:
                model.status = ModelStatus.failed
                model.error_message = str(exc)[:1000]
                await session.flush()
        raise

    async with AsyncSessionMaker() as session:
        model = await _load_model(session, model_id)
        if model is None:
            return
        model.status = ModelStatus.ready
        model.units = result.units
        model.element_count = result.element_count
        model.bbox = result.bbox
        if result.xkt_file_id is not None:
            model.xkt_file_id = result.xkt_file_id
        for disc in result.disciplines:
            session.add(
                ModelDiscipline(
                    model_id=model_id,
                    name=disc.name,
                    element_count=disc.element_count,
                )
            )
        await session.flush()


# Internals


class _Discipline:
    """In-memory representation of a parsed discipline before the
    row is persisted."""

    __slots__ = ("element_count", "name")

    def __init__(self, name: str, element_count: int) -> None:
        self.name = name
        self.element_count = element_count


class _ParseResult:
    __slots__ = ("bbox", "disciplines", "element_count", "units", "xkt_file_id")

    def __init__(
        self,
        units: str | None,
        element_count: int,
        bbox: dict[str, object] | None,
        disciplines: list[_Discipline],
        xkt_file_id: UUID | None = None,
    ) -> None:
        self.units = units
        self.element_count = element_count
        self.bbox = bbox
        self.disciplines = disciplines
        self.xkt_file_id = xkt_file_id


async def _load_model(session: object, model_id: UUID) -> FederatedModel | None:
    stmt = select(FederatedModel).where(FederatedModel.id == model_id)
    result = await session.execute(stmt)  # type: ignore[attr-defined]
    return result.scalar_one_or_none()


async def _run_ifc_convert(model_id: UUID) -> _ParseResult:
    """Stream the IFC bytes to a temp dir, run IfcConvert, parse the
    metadata JSON sidecar, upload the XKT to S3 + create a File row,
    and return the result with ``xkt_file_id`` populated.

    The XKT upload happens *inside* the tempdir lifetime so the file
    bytes survive long enough to upload before the ``finally`` cleans
    them. The actor then binds ``xkt_file_id`` onto the FederatedModel
    in its "ready" write.
    """
    workdir = Path(tempfile.mkdtemp(prefix="rapidly-ifc-"))
    try:
        ifc_path = workdir / "source.ifc"
        xkt_path = workdir / "model.xkt"
        meta_path = workdir / "meta.json"

        await _stream_source_to_disk(model_id, ifc_path)

        cmd = [
            "IfcConvert",
            str(ifc_path),
            str(xkt_path),
            "--json-meta",
            str(meta_path),
        ]
        proc = await asyncio.to_thread(
            subprocess.run,
            cmd,
            check=True,
            capture_output=True,
            timeout=_PARSE_TIMEOUT_S,
        )
        _log.info(
            "viewer.parse_ifc.convert_complete",
            model_id=str(model_id),
            stdout_bytes=len(proc.stdout or b""),
        )

        meta = json.loads(meta_path.read_text())
        result = _parse_metadata(meta)
        # Upload the XKT BEFORE the tempdir's finally cleans it. The
        # File row's id is what the actor binds onto the
        # FederatedModel; failures here surface as 'failed' via the
        # actor's exception handler.
        xkt_file_id = await _upload_xkt_and_create_file(model_id, xkt_path)
        result.xkt_file_id = xkt_file_id
        return result
    finally:
        shutil.rmtree(workdir, ignore_errors=True)


# Read chunk size for the S3 stream-to-disk. 1 MiB keeps memory
# pressure bounded on a 250+ MB IFC without making the kernel
# context-switch on every read.
_S3_READ_CHUNK = 1 * 1024 * 1024


async def _stream_source_to_disk(model_id: UUID, dest: Path) -> None:
    """Resolve the model's ``source_file_id`` to bytes and stream
    them onto ``dest``.

    Loads the FederatedModel + its source File row, picks the right
    S3Service from the catalog/file registry, fetches the object,
    and streams the boto3 StreamingBody to disk in 1 MiB chunks so
    the worker doesn't accumulate the full IFC in Python memory.

    Raises ``FileNotFoundError`` if the model or its source row is
    missing — surfaces as ``status='failed'`` with that message in
    the actor's error path.
    """
    from rapidly.catalog.file.s3 import S3_SERVICES
    from rapidly.models import File

    async with AsyncSessionMaker() as session:
        model_stmt = select(FederatedModel).where(FederatedModel.id == model_id)
        model_row = (await session.execute(model_stmt)).scalar_one_or_none()
        if model_row is None:
            raise FileNotFoundError(f"FederatedModel {model_id} not found")
        file_stmt = select(File).where(File.id == model_row.source_file_id)
        file_row = (await session.execute(file_stmt)).scalar_one_or_none()
        if file_row is None:
            raise FileNotFoundError(
                f"Source File {model_row.source_file_id} not found "
                f"for FederatedModel {model_id}"
            )
        # Capture the fields we need before the session closes so we
        # can do the boto3 GetObject + disk write outside the DB
        # transaction. boto3 is sync; we run it in a thread.
        service = file_row.service
        path = file_row.path

    def _download_sync() -> None:
        s3 = S3_SERVICES[service]
        obj = s3.get_object_or_raise(path)
        body = obj.get("Body")
        if body is None:
            raise FileNotFoundError(f"S3 GetObject returned no Body for path={path}")
        with open(dest, "wb") as fh:
            # StreamingBody's .read(n) returns bytes; b"" signals EOF.
            while True:
                chunk = body.read(_S3_READ_CHUNK)
                if not chunk:
                    break
                fh.write(chunk)

    await asyncio.to_thread(_download_sync)


# XKT files can be quite large for a federated model. 10 MiB write
# chunks keep memory bounded for the workspace read but otherwise
# don't matter much — boto3 buffers the put_object body in memory
# anyway. For v1 we read the whole file into a single put_object
# call; multipart upload-for-XKT is a v2 if XKTs routinely exceed
# 100 MB in production.
_XKT_MIME = "application/octet-stream"


async def _upload_xkt_and_create_file(model_id: UUID, xkt_path: Path) -> UUID | None:
    """Upload the XKT bytes at ``xkt_path`` to S3 and create a ``File``
    row pointing at it. Returns the new File's id, or ``None`` if the
    file is empty / oversize (defence-in-depth).

    Resolves the workspace_id via FederatedModel -> Project for the
    File row's tenancy column.

    Raises on any persistence error; the actor catches and writes
    status='failed' with the message.
    """
    from rapidly.catalog.file.s3 import S3_SERVICES
    from rapidly.models import FederatedModel, File, Project
    from rapidly.models.file import FileServiceTypes

    if not xkt_path.exists():
        raise FileNotFoundError(f"XKT not produced at {xkt_path}")
    xkt_bytes = xkt_path.read_bytes()
    size = len(xkt_bytes)
    if size == 0:
        # IfcConvert silently produced an empty file. Defensive guard.
        return None
    if not _xkt_size_ok(size):
        raise ValueError(f"XKT size {size} bytes exceeds cap {_MAX_XKT_BYTES}")

    # Resolve workspace via the model -> project chain.
    async with AsyncSessionMaker() as session:
        join_stmt = (
            select(FederatedModel, Project)
            .join(Project, Project.id == FederatedModel.project_id)
            .where(FederatedModel.id == model_id)
        )
        row = (await session.execute(join_stmt)).first()
        if row is None:
            raise FileNotFoundError(
                f"FederatedModel {model_id} missing during XKT upload"
            )
        _, project = row
        workspace_id = project.workspace_id

    # Storage path under the workspace's tenant prefix. The model_id
    # in the key gives a deterministic 1:1 mapping back to the model
    # for ops debugging.
    s3_path = f"viewer/{workspace_id}/{model_id}/model.xkt"
    service = FileServiceTypes.downloadable
    s3 = S3_SERVICES[service]

    def _upload_sync() -> None:
        s3.upload(data=xkt_bytes, path=s3_path, mime_type=_XKT_MIME)

    await asyncio.to_thread(_upload_sync)

    # Create the File row that the FederatedModel will bind to.
    async with AsyncSessionMaker() as session:
        file_row = File(
            workspace_id=workspace_id,
            name=f"{model_id}.xkt",
            path=s3_path,
            mime_type=_XKT_MIME,
            size=size,
            service=service,
            is_uploaded=True,
            is_enabled=True,
        )
        session.add(file_row)
        await session.flush()
        return file_row.id


def _parse_metadata(meta: dict[str, object]) -> _ParseResult:
    """Project IfcConvert's ``--json-meta`` payload onto our schema.

    The CLI emits a tree with ``units``, ``element_count``, ``bbox``,
    and per-discipline counts under ``disciplines``. Fields we don't
    care about are ignored."""
    units = meta.get("units")
    if units is not None and not isinstance(units, str):
        units = None
    element_count_raw = meta.get("element_count", 0)
    element_count = int(element_count_raw) if isinstance(element_count_raw, int) else 0
    bbox = meta.get("bbox") if isinstance(meta.get("bbox"), dict) else None

    disciplines: list[_Discipline] = []
    raw_disciplines = meta.get("disciplines", [])
    if isinstance(raw_disciplines, list):
        for entry in raw_disciplines:
            if not isinstance(entry, dict):
                continue
            name = entry.get("name")
            count = entry.get("element_count", 0)
            if isinstance(name, str) and isinstance(count, int):
                disciplines.append(_Discipline(name=name, element_count=count))

    return _ParseResult(
        units=units,
        element_count=element_count,
        bbox=bbox,
        disciplines=disciplines,
    )


def _xkt_size_ok(size_bytes: int) -> bool:
    """Defence-in-depth size cap. Exposed at module scope so tests
    can assert the boundary without monkey-patching module globals."""
    return size_bytes <= _MAX_XKT_BYTES
