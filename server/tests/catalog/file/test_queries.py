"""Tests for ``rapidly/catalog/file/queries.py``.

Six load-bearing surfaces of ``FileRepository``:

- ``get_readable_statement`` enforces tenant scope: USER →
  workspaces with active membership; WORKSPACE → own workspace.
  Drift would leak file metadata across tenants.
- ``apply_list_filters`` UNCONDITIONALLY filters to
  ``is_uploaded == True`` so half-completed multipart-upload
  rows never surface in any list view. Drift would surface
  files whose body never finished uploading (placeholders that
  return 4xx when downloaded).
- ``get_selectable_share_media_file`` requires FOUR conjunctive
  gates: uploaded, enabled, not-deleted, AND workspace-scoped.
  Drift to drop any would let half-uploaded / disabled / soft-
  deleted media leak into the storefront, OR surface across
  tenants.
- ``get_pending_scan`` returns files where ``scan_status IS NULL``
  OR ``scan_status == pending``. Drift to require ``IS NULL``
  alone would silently skip retried scans; drift to skip the
  ``is_uploaded`` filter would scan placeholder rows.
- ``delete_share_media_by_file_id`` HARD-deletes ShareMedia rows
  scoped to a single file_id (used during file deletion to
  cascade the join-table cleanup). Drift to UPDATE / drop the
  WHERE would mass-affect every ShareMedia row.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from rapidly.catalog.file.queries import FileRepository


def _compile(stmt: object) -> str:
    return str(stmt.compile(compile_kwargs={"literal_binds": True}))  # type: ignore[attr-defined]


@pytest.mark.asyncio
class TestGetReadableStatement:
    async def test_user_principal_filters_by_membership(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        repo = FileRepository(session=MagicMock())
        principal = MagicMock()
        principal.subject = MagicMock()
        principal.subject.id = uuid4()

        monkeypatch.setattr(
            "rapidly.catalog.file.queries.is_user_principal", lambda p: True
        )
        monkeypatch.setattr(
            "rapidly.catalog.file.queries.is_workspace_principal", lambda p: False
        )

        stmt = repo.get_readable_statement(principal)
        sql = _compile(stmt).lower()
        assert "workspace_memberships.workspace_id" in sql
        assert "workspace_memberships.user_id" in sql
        assert "workspace_memberships.deleted_at is null" in sql

    async def test_workspace_principal_filters_to_own_workspace_id(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        repo = FileRepository(session=MagicMock())
        target = uuid4()
        principal = MagicMock()
        principal.subject = MagicMock()
        principal.subject.id = target

        monkeypatch.setattr(
            "rapidly.catalog.file.queries.is_user_principal", lambda p: False
        )
        monkeypatch.setattr(
            "rapidly.catalog.file.queries.is_workspace_principal", lambda p: True
        )

        stmt = repo.get_readable_statement(principal)
        sql = _compile(stmt).replace("-", "")
        assert target.hex in sql


class TestApplyListFiltersIsUploaded:
    def test_unconditional_is_uploaded_filter(self) -> None:
        # Pin: every list view filters to ``is_uploaded == True``
        # so half-completed multipart-upload placeholder rows
        # never surface. Drift would surface unupload-able files.
        repo = FileRepository(session=MagicMock())
        stmt = repo.get_base_statement()
        stmt = repo.apply_list_filters(stmt)
        sql = _compile(stmt).lower()
        assert "files.is_uploaded is true" in sql

    def test_workspace_id_uses_in_clause(self) -> None:
        repo = FileRepository(session=MagicMock())
        stmt = repo.get_base_statement()
        wid = uuid4()
        stmt = repo.apply_list_filters(stmt, workspace_id=[wid])
        sql = _compile(stmt).replace("-", "")
        assert wid.hex in sql

    def test_ids_uses_in_clause(self) -> None:
        repo = FileRepository(session=MagicMock())
        stmt = repo.get_base_statement()
        fid = uuid4()
        stmt = repo.apply_list_filters(stmt, ids=[fid])
        sql = _compile(stmt).replace("-", "")
        assert fid.hex in sql


@pytest.mark.asyncio
class TestGetSelectableShareMediaFile:
    async def test_requires_all_four_gates(self) -> None:
        # Pin: uploaded + enabled + not-deleted + workspace-scoped.
        # Drift to drop any would let half-uploaded / disabled /
        # soft-deleted media leak into storefront media pickers
        # OR surface across tenants.
        repo = FileRepository(session=MagicMock())
        captured: dict[str, Any] = {}

        async def _exec(stmt: object) -> Any:
            captured["stmt"] = stmt
            r = MagicMock()
            r.scalar_one_or_none.return_value = None
            return r

        repo.session.execute = AsyncMock(side_effect=_exec)  # type: ignore[method-assign]

        wid = uuid4()
        fid = uuid4()
        await repo.get_selectable_share_media_file(fid, workspace_id=wid)

        sql = _compile(captured["stmt"]).lower()
        # Workspace gate.
        assert wid.hex in sql.replace("-", "")
        # File-id gate.
        assert fid.hex in sql.replace("-", "")
        # Three lifecycle gates.
        assert "files.is_uploaded is true" in sql
        assert "files.is_enabled is true" in sql
        assert "files.deleted_at is null" in sql


@pytest.mark.asyncio
class TestGetPendingScan:
    async def test_filters_uploaded_and_pending_or_null_status(self) -> None:
        # Pin: scan-cleanup picks up rows where the body has
        # uploaded AND (scan_status IS NULL OR pending). Drift
        # to require IS NULL alone would skip retried scans;
        # drift to drop is_uploaded would scan placeholders.
        repo = FileRepository(session=MagicMock())
        captured: dict[str, Any] = {}

        async def _capture(stmt: object) -> list[Any]:
            captured["stmt"] = stmt
            return []

        repo.get_all = AsyncMock(side_effect=_capture)  # type: ignore[method-assign]
        await repo.get_pending_scan()

        sql = _compile(captured["stmt"]).lower()
        assert "files.is_uploaded is true" in sql
        assert "files.scan_status is null" in sql
        assert "files.scan_status =" in sql
        assert "'pending'" in sql
        # The two scan-status branches are OR'd.
        assert " or " in sql


@pytest.mark.asyncio
class TestDeleteShareMediaByFileId:
    async def test_hard_delete_scoped_to_single_file(self) -> None:
        # Pin: single-file scope on the WHERE — drift to drop
        # would mass-affect every ShareMedia row.
        repo = FileRepository(session=MagicMock())
        captured: dict[str, Any] = {}

        async def _exec(stmt: object) -> Any:
            captured["stmt"] = stmt
            return MagicMock()

        repo.session.execute = AsyncMock(side_effect=_exec)  # type: ignore[method-assign]

        target = uuid4()
        await repo.delete_share_media_by_file_id(target)

        sql = _compile(captured["stmt"]).lower()
        assert sql.startswith("delete from share_medias")
        assert target.hex in sql.replace("-", "")
