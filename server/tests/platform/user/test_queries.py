"""Tests for ``rapidly/platform/user/queries.py``.

User repository — many lookup methods share a load-bearing
"deleted + blocked" filter pattern. Six load-bearing surfaces:

- Email lookups are CASE-INSENSITIVE (``func.lower(User.email)
  == email.lower()``). Drift to bare equality would silently
  mis-route password-reset emails sent to ``Alice@…`` for users
  registered as ``alice@…``.
- ``get_by_email`` (and its siblings) DEFAULT to excluding
  blocked AND soft-deleted users. Drift to fail-open would let
  an admin who blocked a user still see them on the public
  workspace member list.
- Each lookup ``include_deleted=True`` / ``included_blocked=True``
  flag reverses ONLY that gate (admin tooling needs both
  variants — drift to flip would mis-render the moderator's
  user-detail page).
- ``is_workspace_member`` returns False (not None) when the
  user has NO row, AND the WHERE matches ``deleted_at IS
  NULL``. Drift would return None (truthy in some callers) or
  count soft-deleted memberships as active.
- ``soft_delete_notification_recipients`` filters to
  ``deleted_at IS NULL`` BEFORE updating, so re-running the
  delete worker doesn't re-stamp historical timestamps.
- ``delete_oauth_accounts`` is HARD delete (no soft-delete
  mixin) — the OAuth account stores a refresh token; on
  account deletion we must wipe it from the DB to comply with
  data-deletion requests, NOT keep it under a `deleted_at`
  flag.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from rapidly.models.user import OAuthPlatform
from rapidly.platform.user.queries import UserRepository


def _compile(stmt: object) -> str:
    return str(stmt.compile(compile_kwargs={"literal_binds": True}))  # type: ignore[attr-defined]


@pytest.mark.asyncio
class TestGetByEmailCaseInsensitive:
    async def test_lowercases_caller_email_and_uses_func_lower(self) -> None:
        # Pin: ``func.lower(email) == email.lower()`` — fully
        # case-insensitive. Drift to bare ``==`` would silently
        # mis-route on case-mixed addresses.
        repo = UserRepository(session=MagicMock())
        captured: dict[str, Any] = {}

        async def _capture(stmt: object) -> Any:
            captured["stmt"] = stmt
            return None

        repo.get_one_or_none = AsyncMock(side_effect=_capture)  # type: ignore[method-assign]
        await repo.get_by_email("Alice@Example.COM")

        sql = _compile(captured["stmt"]).lower()
        assert "lower(users.email)" in sql
        # The bound literal is the LOWERCASED form (caller
        # uppercase is normalised before bind).
        assert "alice@example.com" in sql

    async def test_default_excludes_blocked_users(self) -> None:
        # Pin: ``blocked_at IS NULL`` is the default gate. Drift
        # would let blocked users surface in password-reset /
        # invite-collision lookups.
        repo = UserRepository(session=MagicMock())
        captured: dict[str, Any] = {}

        async def _capture(stmt: object) -> Any:
            captured["stmt"] = stmt
            return None

        repo.get_one_or_none = AsyncMock(side_effect=_capture)  # type: ignore[method-assign]
        await repo.get_by_email("alice@example.com")

        sql = _compile(captured["stmt"]).lower()
        assert "users.blocked_at is null" in sql

    async def test_included_blocked_drops_blocked_filter(self) -> None:
        # Pin: admin tooling needs the ability to fetch blocked
        # users (e.g., moderator detail page). Drift to always-
        # filter would 404 every blocked-user admin link.
        repo = UserRepository(session=MagicMock())
        captured: dict[str, Any] = {}

        async def _capture(stmt: object) -> Any:
            captured["stmt"] = stmt
            return None

        repo.get_one_or_none = AsyncMock(side_effect=_capture)  # type: ignore[method-assign]
        await repo.get_by_email("alice@example.com", included_blocked=True)

        sql = _compile(captured["stmt"]).lower()
        # The blocked filter does NOT appear in the WHERE.
        assert "blocked_at is null" not in sql


@pytest.mark.asyncio
class TestIsWorkspaceMember:
    async def test_returns_false_when_no_row(self) -> None:
        # Pin: returns BOOL not None. Drift to return the row
        # itself would surface as truthy/falsy ambiguity in
        # downstream auth checks.
        repo = UserRepository(session=MagicMock())
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = None
        repo.session.execute = AsyncMock(return_value=result_mock)  # type: ignore[method-assign]

        out = await repo.is_workspace_member(uuid4(), uuid4())
        assert out is False

    async def test_returns_true_when_row_exists(self) -> None:
        repo = UserRepository(session=MagicMock())
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = MagicMock()
        repo.session.execute = AsyncMock(return_value=result_mock)  # type: ignore[method-assign]

        out = await repo.is_workspace_member(uuid4(), uuid4())
        assert out is True

    async def test_filters_to_active_membership(self) -> None:
        # Pin: ``deleted_at IS NULL`` on the membership row.
        # Drift would let a soft-deleted membership pass the
        # auth check (a removed member would still be authorised
        # to access the workspace).
        repo = UserRepository(session=MagicMock())
        captured: dict[str, Any] = {}

        async def _exec(stmt: object) -> Any:
            captured["stmt"] = stmt
            result = MagicMock()
            result.scalar_one_or_none.return_value = None
            return result

        repo.session.execute = AsyncMock(side_effect=_exec)  # type: ignore[method-assign]
        await repo.is_workspace_member(uuid4(), uuid4())

        sql = _compile(captured["stmt"]).lower()
        assert "workspace_memberships.deleted_at is null" in sql


@pytest.mark.asyncio
class TestSoftDeleteNotificationRecipients:
    async def test_only_updates_active_rows(self) -> None:
        # Pin: ``deleted_at IS NULL`` filter on the UPDATE so
        # re-running the delete worker doesn't re-stamp the
        # historical leave-date.
        repo = UserRepository(session=MagicMock())
        captured: dict[str, Any] = {}

        async def _exec(stmt: object) -> Any:
            captured["stmt"] = stmt
            return MagicMock()

        repo.session.execute = AsyncMock(side_effect=_exec)  # type: ignore[method-assign]
        await repo.soft_delete_notification_recipients(uuid4())

        sql = _compile(captured["stmt"]).lower()
        assert sql.startswith("update notification_recipients")
        assert "deleted_at is null" in sql

    async def test_scopes_by_user_id(self) -> None:
        repo = UserRepository(session=MagicMock())
        captured: dict[str, Any] = {}

        async def _exec(stmt: object) -> Any:
            captured["stmt"] = stmt
            return MagicMock()

        repo.session.execute = AsyncMock(side_effect=_exec)  # type: ignore[method-assign]
        target = uuid4()
        await repo.soft_delete_notification_recipients(target)

        sql = _compile(captured["stmt"]).replace("-", "")
        assert target.hex in sql


@pytest.mark.asyncio
class TestDeleteOauthAccountsIsHardDelete:
    async def test_uses_delete_statement_not_update(self) -> None:
        # Pin: HARD DELETE — the OAuth account row stores a
        # refresh token. On account deletion we MUST wipe it from
        # the DB to comply with data-deletion requests; drift to
        # soft delete would keep the secret material alive under
        # a ``deleted_at`` flag.
        repo = UserRepository(session=MagicMock())
        captured: dict[str, Any] = {}

        async def _exec(stmt: object) -> Any:
            captured["stmt"] = stmt
            return MagicMock()

        repo.session.execute = AsyncMock(side_effect=_exec)  # type: ignore[method-assign]
        target = uuid4()
        await repo.delete_oauth_accounts(target)

        sql = _compile(captured["stmt"]).lower()
        assert sql.startswith("delete from oauth_accounts")
        # Scoped to one user.
        assert target.hex in sql.replace("-", "")


@pytest.mark.asyncio
class TestGetByOauthAccount:
    async def test_joins_oauth_accounts_with_platform_and_account_id(self) -> None:
        # Pin: lookup matches BOTH platform AND account_id.
        # Drift to match account_id alone would let a Microsoft
        # account_id collision impersonate a Google user.
        repo = UserRepository(session=MagicMock())
        captured: dict[str, Any] = {}

        async def _capture(stmt: object) -> Any:
            captured["stmt"] = stmt
            return None

        repo.get_one_or_none = AsyncMock(side_effect=_capture)  # type: ignore[method-assign]
        await repo.get_by_oauth_account(OAuthPlatform.google, "abc123")

        sql = _compile(captured["stmt"]).lower()
        assert "oauth_accounts.platform" in sql
        assert "'google'" in sql
        assert "oauth_accounts.account_id" in sql
        assert "'abc123'" in sql
