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
        # xkt_file_id is set by the M3.1c post-actor hook once the
        # XKT staged in the tempdir is uploaded to S3 and a
        # catalog/file row is created.
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
    __slots__ = ("bbox", "disciplines", "element_count", "units")

    def __init__(
        self,
        units: str | None,
        element_count: int,
        bbox: dict[str, object] | None,
        disciplines: list[_Discipline],
    ) -> None:
        self.units = units
        self.element_count = element_count
        self.bbox = bbox
        self.disciplines = disciplines


async def _load_model(session: object, model_id: UUID) -> FederatedModel | None:
    stmt = select(FederatedModel).where(FederatedModel.id == model_id)
    result = await session.execute(stmt)  # type: ignore[attr-defined]
    return result.scalar_one_or_none()


async def _run_ifc_convert(model_id: UUID) -> _ParseResult:
    """Stream the IFC bytes to a temp dir, run IfcConvert, parse the
    metadata JSON sidecar, and return the result. The XKT staging +
    S3 upload happens in M3.1c."""
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
        return _parse_metadata(meta)
    finally:
        shutil.rmtree(workdir, ignore_errors=True)


async def _stream_source_to_disk(model_id: UUID, dest: Path) -> None:
    """Resolve the model's source_file_id to bytes and stage them at
    ``dest``. Implementation is M3.1c — for now we surface a clear
    error so the worker tells the user "the asset pipe isn't wired"
    rather than hanging on a half-stub."""
    raise NotImplementedError(
        "M3.1c — wire the catalog/file S3 streamer into the worker"
    )


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
