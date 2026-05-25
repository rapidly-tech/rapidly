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

    async def test_raises_clear_error_when_streamer_not_wired(self) -> None:
        # M3.1c will wire ``_stream_source_to_disk``; until then the
        # worker should fail loudly with a NotImplementedError so the
        # operator sees a clear diagnostic in the failed row's
        # error_message.
        with pytest.raises(NotImplementedError, match="M3.1c"):
            await workers._run_ifc_convert(uuid4())

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

        with patch(
            "rapidly.viewer.federated_model.workers._stream_source_to_disk",
            _fake_stream,
        ):
            with patch(
                "rapidly.viewer.federated_model.workers.subprocess.run",
                fake_run,
            ):
                result = await workers._run_ifc_convert(uuid4())

        assert len(captured) == 1
        assert captured[0][0] == "IfcConvert"
        assert "--json-meta" in captured[0]
        assert result.units == "mm"
        assert result.element_count == 7
        assert len(result.disciplines) == 1


# NOTE: actor-level integration tests live in M3.1c.
#
# The ``@actor`` decorator wraps the function in a JobQueueManager
# + RedisMiddleware context that's awkward to mock in pure unit
# tests — it requires a live broker stub. The actor body itself is
# thin (load model, check status, dispatch to _run_ifc_convert,
# write result back), and the helpers it dispatches to are covered
# above. End-to-end status-machine assertions get a proper DB
# fixture in M3.1c.
