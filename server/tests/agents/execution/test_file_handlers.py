"""Tests for the file_read + file_write node handlers.

Schema validation only — the S3 + DB paths are exercised via the
existing catalog/file integration tests. Asserting handler-side
validation rules here keeps the unit test fast (no real S3 or DB).
"""

from __future__ import annotations

import pytest

from rapidly.agents.execution.handlers.file_io import (
    FileNodeError,
    file_read_handler,
    file_write_handler,
)


@pytest.mark.asyncio
class TestFileReadValidation:
    async def test_requires_file_id(self) -> None:
        with pytest.raises(FileNodeError, match="file_id is required"):
            await file_read_handler({}, {}, {})

    async def test_rejects_non_uuid_file_id(self) -> None:
        with pytest.raises(FileNodeError, match="not a UUID"):
            await file_read_handler({}, {"file_id": "abc"}, {})


@pytest.mark.asyncio
class TestFileWriteValidation:
    async def test_requires_workspace_id_and_name(self) -> None:
        with pytest.raises(FileNodeError, match="workspace_id and name"):
            await file_write_handler({}, {}, {})

    async def test_rejects_non_uuid_workspace_id(self) -> None:
        with pytest.raises(FileNodeError, match="not a UUID"):
            await file_write_handler({}, {"workspace_id": "abc", "name": "x"}, {})

    async def test_requires_text_or_bytes(self) -> None:
        # Use a real UUID so we get past the UUID-shape check and
        # land on the body-required check.
        from uuid import uuid4

        with pytest.raises(FileNodeError, match=r"\{text, bytes_b64\}"):
            await file_write_handler(
                {}, {"workspace_id": str(uuid4()), "name": "x"}, {}
            )

    async def test_rejects_invalid_base64(self) -> None:
        from uuid import uuid4

        with pytest.raises(FileNodeError, match="not valid base64"):
            await file_write_handler(
                {},
                {
                    "workspace_id": str(uuid4()),
                    "name": "x",
                    "bytes_b64": "@@@not-base64@@@",
                },
                {},
            )
