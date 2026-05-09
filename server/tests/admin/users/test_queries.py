"""Tests for ``rapidly/admin/users/queries.py``.

Two load-bearing surfaces (one per method) plus a privacy guard:

- ``get_active_oauth_accounts`` selects ONLY rows where
  ``deleted_at IS NULL``. Drift to ``IS NOT NULL`` would show
  deleted OAuth accounts as active in the admin user-detail
  page (UX confusion + a privacy hazard if the user has
  re-disconnected an account they wanted gone).
- ``get_deleted_oauth_accounts`` selects ONLY rows where
  ``deleted_at IS NOT NULL`` (the mirror of the above).
- Both methods scope by ``user_id``. Drift to drop the user_id
  filter would leak EVERY user's OAuth accounts into the admin
  detail view of any one user — a privacy bug.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from rapidly.admin.users.queries import AdminUserRepository


def _compile(stmt: object) -> str:
    return str(stmt.compile(compile_kwargs={"literal_binds": True}))  # type: ignore[attr-defined]


@pytest.mark.asyncio
class TestGetActiveOauthAccounts:
    async def test_filters_to_non_deleted_rows(self) -> None:
        # Pin: ``deleted_at IS NULL`` (active rows only). Drift
        # to ``IS NOT NULL`` would surface DELETED accounts in
        # the admin's "currently linked" panel.
        repo = AdminUserRepository(session=MagicMock())
        captured: dict[str, object] = {}

        async def _capture(stmt: object) -> list[object]:
            captured["stmt"] = stmt
            return []

        repo.get_all = AsyncMock(side_effect=_capture)  # type: ignore[method-assign]
        await repo.get_active_oauth_accounts(uuid4())

        sql = _compile(captured["stmt"]).lower()
        assert "deleted_at is null" in sql
        assert "is not null" not in sql

    async def test_scopes_to_supplied_user_id(self) -> None:
        # Pin: privacy guard — user_id filter MUST be present.
        # Drift to drop it would leak every user's OAuth
        # accounts into one user's admin detail view.
        repo = AdminUserRepository(session=MagicMock())
        captured: dict[str, object] = {}

        async def _capture(stmt: object) -> list[object]:
            captured["stmt"] = stmt
            return []

        repo.get_all = AsyncMock(side_effect=_capture)  # type: ignore[method-assign]
        target_id = uuid4()
        await repo.get_active_oauth_accounts(target_id)

        sql = _compile(captured["stmt"])
        assert "user_id" in sql.lower()
        # The literal-bound UUID (dashless) appears in the SQL.
        assert target_id.hex in sql.replace("-", "")


@pytest.mark.asyncio
class TestGetDeletedOauthAccounts:
    async def test_filters_to_deleted_rows(self) -> None:
        # Pin: ``deleted_at IS NOT NULL`` (deleted rows only).
        # Drift to ``IS NULL`` would surface ACTIVE accounts in
        # the admin's "previously disconnected" panel.
        repo = AdminUserRepository(session=MagicMock())
        captured: dict[str, object] = {}

        async def _capture(stmt: object) -> list[object]:
            captured["stmt"] = stmt
            return []

        repo.get_all = AsyncMock(side_effect=_capture)  # type: ignore[method-assign]
        await repo.get_deleted_oauth_accounts(uuid4())

        sql = _compile(captured["stmt"]).lower()
        assert "deleted_at is not null" in sql

    async def test_scopes_to_supplied_user_id(self) -> None:
        # Pin: privacy guard — same as the active case.
        repo = AdminUserRepository(session=MagicMock())
        captured: dict[str, object] = {}

        async def _capture(stmt: object) -> list[object]:
            captured["stmt"] = stmt
            return []

        repo.get_all = AsyncMock(side_effect=_capture)  # type: ignore[method-assign]
        target_id = uuid4()
        await repo.get_deleted_oauth_accounts(target_id)

        sql = _compile(captured["stmt"])
        assert "user_id" in sql.lower()
        assert target_id.hex in sql.replace("-", "")


class TestRepositoryShape:
    def test_model_is_oauth_account(self) -> None:
        # Pin: the repository targets ``OAuthAccount``, not the
        # ``User`` model. Drift would silently break every admin
        # OAuth-list call site.
        from rapidly.models.user import OAuthAccount

        assert AdminUserRepository.model is OAuthAccount
