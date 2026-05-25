"""Tests for the IFC parse worker.

Pure-unit: the subprocess + S3 streamer are mocked so the test runs
without IfcConvert or MinIO installed. The actor's session-write
contract + the metadata projection are what we assert.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from rapidly.viewer.federated_model import workers


def test_xkt_size_ok_accepts_under_cap() -> None:
    # 2 GB cap; values at and below pass.
    assert workers._xkt_size_ok(0) is True
    assert workers._xkt_size_ok(1_000_000) is True
    assert workers._xkt_size_ok(2 * 1024 * 1024 * 1024) is True


def test_xkt_size_ok_rejects_over_cap() -> None:
    assert workers._xkt_size_ok(2 * 1024 * 1024 * 1024 + 1) is False


class TestParseMetadata:
    def test_extracts_units_element_count_bbox(self) -> None:
        meta = {
            "units": "mm",
            "element_count": 4182,
            "bbox": {"min": [0, 0, 0], "max": [50, 30, 12]},
            "disciplines": [],
        }
        result = workers._parse_metadata(meta)
        assert result.units == "mm"
        assert result.element_count == 4182
        assert result.bbox == {"min": [0, 0, 0], "max": [50, 30, 12]}
        assert result.disciplines == []

    def test_drops_disciplines_with_bad_shape(self) -> None:
        meta = {
            "units": "m",
            "element_count": 1,
            "bbox": None,
            "disciplines": [
                {"name": "Architecture", "element_count": 100},
                {"name": "Structure", "element_count": "lots"},  # bad type
                "not-a-dict",  # bad shape
                {"name": 42, "element_count": 5},  # bad name
            ],
        }
        result = workers._parse_metadata(meta)
        assert len(result.disciplines) == 1
        assert result.disciplines[0].name == "Architecture"
        assert result.disciplines[0].element_count == 100

    def test_tolerates_missing_fields(self) -> None:
        # Bare ``{}`` should yield a zero-filled result rather than
        # raising — the worker calls this with whatever the CLI
        # produces and we'd rather degrade than fail-loud here.
        result = workers._parse_metadata({})
        assert result.units is None
        assert result.element_count == 0
        assert result.bbox is None
        assert result.disciplines == []

    def test_units_type_coerced_to_none(self) -> None:
        # An integer 'units' field is non-conforming; clear it
        # rather than letting a bad value reach the DB column.
        result = workers._parse_metadata({"units": 42, "element_count": 0})
        assert result.units is None


@pytest.mark.asyncio
class TestRunIfcConvert:
    """The subprocess path. Fully mocked — we never call IfcConvert."""

    async def test_invokes_subprocess_with_expected_cli(self) -> None:
        # With the streamer mocked, the worker should produce the
        # IfcConvert subprocess call and parse the resulting metadata.
        captured: list[list[str]] = []

        async def _fake_stream(_model_id, dest: Path) -> None:
            dest.write_bytes(b"fake-ifc")

        fake_meta = {
            "units": "mm",
            "element_count": 7,
            "bbox": {"min": [0, 0, 0], "max": [1, 1, 1]},
            "disciplines": [{"name": "Architecture", "element_count": 7}],
        }

        def fake_run(cmd: list[str], **_kwargs: object) -> MagicMock:
            captured.append(cmd)
            # Mimic IfcConvert: write the meta sidecar to the path
            # the worker passed as the 4th argument.
            meta_idx = cmd.index("--json-meta")
            meta_path = Path(cmd[meta_idx + 1])
            import json

            meta_path.write_text(json.dumps(fake_meta))
            proc = MagicMock()
            proc.stdout = b""
            return proc

        async def _fake_upload(_model_id, _xkt_path) -> object:
            # M3.1d wired the XKT upload into _run_ifc_convert; the
            # unit test doesn't exercise it (covered by
            # TestUploadXktAndCreateFile below). Stub to a fake id
            # so the convert flow completes.
            return uuid4()

        with patch(
            "rapidly.viewer.federated_model.workers._stream_source_to_disk",
            _fake_stream,
        ):
            with patch(
                "rapidly.viewer.federated_model.workers.subprocess.run",
                fake_run,
            ):
                with patch(
                    "rapidly.viewer.federated_model.workers._upload_xkt_and_create_file",
                    _fake_upload,
                ):
                    result = await workers._run_ifc_convert(uuid4())

        assert len(captured) == 1
        assert captured[0][0] == "IfcConvert"
        assert "--json-meta" in captured[0]
        assert result.units == "mm"
        assert result.element_count == 7
        assert len(result.disciplines) == 1


@pytest.mark.asyncio
class TestStreamSourceToDisk:
    """The S3 stream-to-disk path. Mocks the boto3 GetObject so the
    test runs without MinIO + without a real DB."""

    async def test_streams_chunks_to_dest_file(self, tmp_path: Path) -> None:
        # Fake StreamingBody — .read(n) returns bytes; b"" on EOF.
        chunks = [b"chunk-1-", b"chunk-2-", b"chunk-3", b""]

        class FakeBody:
            def __init__(self) -> None:
                self._i = 0

            def read(self, _n: int) -> bytes:
                out = chunks[self._i]
                self._i += 1
                return out

        fake_s3 = MagicMock()
        fake_s3.get_object_or_raise.return_value = {"Body": FakeBody()}

        # FederatedModel + File lookups: synthesise minimal stand-ins.
        from rapidly.models import FederatedModel, File, ModelStatus

        fake_model = MagicMock(spec=FederatedModel)
        fake_model.source_file_id = uuid4()
        fake_model.status = ModelStatus.uploaded
        fake_file = MagicMock(spec=File)
        fake_file.service = "rapidly-files"
        fake_file.path = "tenant/abc/source.ifc"

        # AsyncSessionMaker → session → session.execute returns a
        # scalar_one_or_none() projection. We need the result to
        # change per query: first call returns the model, second
        # call returns the file.
        from unittest.mock import AsyncMock

        results = [
            MagicMock(scalar_one_or_none=MagicMock(return_value=fake_model)),
            MagicMock(scalar_one_or_none=MagicMock(return_value=fake_file)),
        ]
        session = MagicMock()
        session.execute = AsyncMock(side_effect=results)
        session.__aenter__ = AsyncMock(return_value=session)
        session.__aexit__ = AsyncMock(return_value=False)

        dest = tmp_path / "streamed.ifc"
        with patch(
            "rapidly.viewer.federated_model.workers.AsyncSessionMaker",
            return_value=session,
        ):
            with patch.dict(
                "rapidly.catalog.file.s3.S3_SERVICES",
                {"rapidly-files": fake_s3},
                clear=False,
            ):
                await workers._stream_source_to_disk(uuid4(), dest)

        assert dest.exists()
        assert dest.read_bytes() == b"chunk-1-chunk-2-chunk-3"
        fake_s3.get_object_or_raise.assert_called_once_with("tenant/abc/source.ifc")

    async def test_raises_file_not_found_when_model_missing(
        self, tmp_path: Path
    ) -> None:
        from unittest.mock import AsyncMock

        results = [MagicMock(scalar_one_or_none=MagicMock(return_value=None))]
        session = MagicMock()
        session.execute = AsyncMock(side_effect=results)
        session.__aenter__ = AsyncMock(return_value=session)
        session.__aexit__ = AsyncMock(return_value=False)

        dest = tmp_path / "should-not-exist.ifc"
        with patch(
            "rapidly.viewer.federated_model.workers.AsyncSessionMaker",
            return_value=session,
        ):
            with pytest.raises(FileNotFoundError, match="FederatedModel"):
                await workers._stream_source_to_disk(uuid4(), dest)
        assert not dest.exists()


@pytest.mark.asyncio
class TestUploadXktAndCreateFile:
    """The XKT-upload + File-row path. boto3 + DB are mocked."""

    async def test_returns_none_on_empty_xkt(self, tmp_path: Path) -> None:
        # IfcConvert silently producing an empty file shouldn't crash
        # the worker; return None so the actor leaves xkt_file_id
        # null + still marks status='ready' (the engineer can
        # re-trigger with a known-good IFC).
        empty = tmp_path / "model.xkt"
        empty.write_bytes(b"")
        result = await workers._upload_xkt_and_create_file(uuid4(), empty)
        assert result is None

    async def test_raises_when_xkt_missing(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError, match="XKT not produced"):
            await workers._upload_xkt_and_create_file(uuid4(), tmp_path / "missing.xkt")

    async def test_raises_when_xkt_oversize(self, tmp_path: Path) -> None:
        # Defence-in-depth: > 2 GB rejects. Use the cap helper to
        # avoid actually writing 2 GB of bytes in test.
        big = tmp_path / "huge.xkt"
        big.write_bytes(b"x")
        # Monkey-patch the cap-checker for a tight test boundary.
        from unittest.mock import patch as _patch

        with _patch(
            "rapidly.viewer.federated_model.workers._xkt_size_ok",
            return_value=False,
        ):
            with pytest.raises(ValueError, match="exceeds cap"):
                await workers._upload_xkt_and_create_file(uuid4(), big)


# NOTE: full actor-level integration tests with a real DB live in
# a follow-up. The actor body itself (load model, dispatch helpers,
# write result back) is thin and is covered by the individual
# helper tests above.
#
# The ``@actor`` decorator wraps the function in a JobQueueManager
# + RedisMiddleware context that's awkward to mock in pure unit
# tests — it requires a live broker stub. The actor body itself is
# thin (load model, check status, dispatch to _run_ifc_convert,
# write result back), and the helpers it dispatches to are covered
# above. End-to-end status-machine assertions get a proper DB
# fixture in M3.1c.
