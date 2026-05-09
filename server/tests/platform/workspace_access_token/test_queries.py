"""Tests for ``rapidly/platform/workspace_access_token/queries.py``.

OAT (workspace access token) repository. Five load-bearing surfaces:

- ``get_by_token_hash`` ALWAYS gates on ``Workspace.can_authenticate``
  — drift to drop would let tokens for blocked / suspended
  workspaces still authenticate (the workspace's
  ``can_authenticate`` flag is the kill switch).
- ``get_by_token_hash`` excludes EXPIRED tokens by default
  (``expires_at IS NULL OR expires_at > now()``). Drift would
  let an expired token still authenticate; drift to inverted
  bound would block valid tokens.
- ``get_readable_statement`` enforces tenant scope: USER
  principals see ONLY tokens for workspaces they're a member of
  (with the membership's own ``deleted_at IS NULL`` gate);
  WORKSPACE principals see ONLY their own workspace's tokens.
  Drift would leak tokens across tenants.
- ``record_usage`` UPDATE filters by token id only and writes
  the supplied timestamp (drift to update without WHERE would
  stamp every token's last_used).
- ``count_by_workspace_id`` filters to active (non-deleted)
  tokens AND returns 0 (not None) on an empty workspace —
  drift would miscount on the per-token API limit and mis-bill
  the workspace.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from rapidly.platform.workspace_access_token.queries import (
    WorkspaceAccessTokenRepository,
)


def _compile(stmt: object) -> str:
    return str(stmt.compile(compile_kwargs={"literal_binds": True}))  # type: ignore[attr-defined]


@pytest.mark.asyncio
class TestGetByTokenHash:
    async def test_filters_by_workspace_can_authenticate_flag(self) -> None:
        # Pin: blocked / deleted workspaces' tokens MUST NOT
        # authenticate. ``Workspace.can_authenticate`` is a
        # hybrid_property that resolves to
        # ``deleted_at IS NULL AND blocked_at IS NULL`` — those
        # two predicates together are the kill switch. Drift
        # would let stale tokens persist after a workspace ban
        # OR after the workspace itself is soft-deleted.
        repo = WorkspaceAccessTokenRepository(session=MagicMock())
        captured: dict[str, Any] = {}

        async def _capture(stmt: object) -> Any:
            captured["stmt"] = stmt
            return None

        repo.get_one_or_none = AsyncMock(side_effect=_capture)  # type: ignore[method-assign]
        await repo.get_by_token_hash("hash_abc")

        sql = _compile(captured["stmt"]).lower()
        # Both gates of the can_authenticate hybrid property
        # appear in the WHERE.
        assert "workspaces.deleted_at is null" in sql
        assert "workspaces.blocked_at is null" in sql

    async def test_default_excludes_expired_tokens(self) -> None:
        # Pin: ``expires_at IS NULL OR expires_at > now()``.
        # Drift would let an expired token still authenticate.
        repo = WorkspaceAccessTokenRepository(session=MagicMock())
        captured: dict[str, Any] = {}

        async def _capture(stmt: object) -> Any:
            captured["stmt"] = stmt
            return None

        repo.get_one_or_none = AsyncMock(side_effect=_capture)  # type: ignore[method-assign]
        await repo.get_by_token_hash("hash_abc")

        sql = _compile(captured["stmt"]).lower()
        assert "expires_at is null" in sql
        assert "expires_at >" in sql
        # OR-combined.
        assert " or " in sql

    async def test_expired_flag_drops_expiry_filter(self) -> None:
        # Pin: ``expired=True`` is the admin/audit path that needs
        # to inspect even-expired tokens. Drift to always-filter
        # would 404 on every admin token-detail page.
        repo = WorkspaceAccessTokenRepository(session=MagicMock())
        captured: dict[str, Any] = {}

        async def _capture(stmt: object) -> Any:
            captured["stmt"] = stmt
            return None

        repo.get_one_or_none = AsyncMock(side_effect=_capture)  # type: ignore[method-assign]
        await repo.get_by_token_hash("hash_abc", expired=True)

        sql = _compile(captured["stmt"]).lower()
        # The expiry OR-clause is absent.
        assert "expires_at >" not in sql

    async def test_filters_by_token_hash(self) -> None:
        # Pin: lookup matches the supplied hash literally —
        # drift to substring or LIKE would surface MULTIPLE
        # tokens to the auth handler.
        repo = WorkspaceAccessTokenRepository(session=MagicMock())
        captured: dict[str, Any] = {}

        async def _capture(stmt: object) -> Any:
            captured["stmt"] = stmt
            return None

        repo.get_one_or_none = AsyncMock(side_effect=_capture)  # type: ignore[method-assign]
        await repo.get_by_token_hash("hash_abc")

        sql = _compile(captured["stmt"]).lower()
        assert "workspace_access_tokens.token" in sql
        assert "= 'hash_abc'" in sql


class TestGetReadableStatementUser:
    def test_user_principal_filters_to_workspaces_user_belongs_to(self) -> None:
        # Pin: USER principals see ONLY their own workspaces'
        # tokens (membership-scoped). Drift would leak tokens
        # across tenants.
        repo = WorkspaceAccessTokenRepository(session=MagicMock())
        user = MagicMock()
        user.id = uuid4()

        # Build a minimal user-principal that satisfies
        # ``is_user_principal``.
        from rapidly.identity.auth.models import AuthPrincipal
        from rapidly.models.user import User

        principal = MagicMock(spec=AuthPrincipal)
        principal.subject = MagicMock(spec=User)
        principal.subject.id = user.id

        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(
                "rapidly.platform.workspace_access_token.queries.is_user_principal",
                lambda p: True,
            )
            mp.setattr(
                "rapidly.platform.workspace_access_token.queries.is_workspace_principal",
                lambda p: False,
            )

            stmt = repo.get_readable_statement(principal)

        sql = _compile(stmt).lower()
        # The subquery into workspace_memberships appears.
        assert "workspace_memberships.workspace_id" in sql
        assert "workspace_memberships.user_id" in sql
        # And the membership's own soft-delete gate.
        assert "workspace_memberships.deleted_at is null" in sql

    def test_workspace_principal_filters_to_own_workspace_id(self) -> None:
        # Pin: WORKSPACE principals see ONLY tokens for their
        # own workspace. Drift would let a workspace token list
        # other workspaces' tokens (massive cross-tenant leak).
        repo = WorkspaceAccessTokenRepository(session=MagicMock())
        from rapidly.identity.auth.models import AuthPrincipal
        from rapidly.models.workspace import Workspace as WorkspaceModel

        principal = MagicMock(spec=AuthPrincipal)
        principal.subject = MagicMock(spec=WorkspaceModel)
        target = uuid4()
        principal.subject.id = target

        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(
                "rapidly.platform.workspace_access_token.queries.is_user_principal",
                lambda p: False,
            )
            mp.setattr(
                "rapidly.platform.workspace_access_token.queries.is_workspace_principal",
                lambda p: True,
            )

            stmt = repo.get_readable_statement(principal)

        sql = _compile(stmt).replace("-", "")
        assert target.hex in sql


@pytest.mark.asyncio
class TestRecordUsage:
    async def test_update_scoped_by_id_only(self) -> None:
        # Pin: WHERE clause matches the single token id (no
        # mass-update). Drift to drop the WHERE would stamp
        # every token's ``last_used_at``.
        repo = WorkspaceAccessTokenRepository(session=MagicMock())
        captured: dict[str, Any] = {}

        async def _exec(stmt: object) -> Any:
            captured["stmt"] = stmt
            return MagicMock()

        repo.session.execute = AsyncMock(side_effect=_exec)  # type: ignore[method-assign]

        from datetime import UTC, datetime

        token_id = uuid4()
        ts = datetime(2026, 4, 25, 12, 0, tzinfo=UTC)
        await repo.record_usage(token_id, ts)

        sql = _compile(captured["stmt"]).lower()
        assert sql.startswith("update workspace_access_tokens")
        assert "last_used_at" in sql
        # The WHERE narrows to the supplied id.
        assert token_id.hex in sql.replace("-", "")
        # And the timestamp literal appears.
        assert "2026-04-25" in sql


@pytest.mark.asyncio
class TestCountByWorkspaceId:
    async def test_excludes_soft_deleted_tokens(self) -> None:
        # Pin: deleted tokens shouldn't count toward the per-
        # workspace API limit. Drift would over-bill / over-
        # restrict on stale rows.
        repo = WorkspaceAccessTokenRepository(session=MagicMock())
        captured: dict[str, Any] = {}

        async def _scalar(stmt: object) -> Any:
            captured["stmt"] = stmt
            return 0

        repo.session.scalar = AsyncMock(side_effect=_scalar)  # type: ignore[method-assign]
        await repo.count_by_workspace_id(uuid4())

        sql = _compile(captured["stmt"]).lower()
        assert "deleted_at is null" in sql
        assert "count(" in sql

    async def test_returns_zero_when_no_rows(self) -> None:
        # Pin: ``None`` from scalar() returns 0 (callers compare
        # against int seat-cap; None comparisons would crash).
        repo = WorkspaceAccessTokenRepository(session=MagicMock())
        repo.session.scalar = AsyncMock(return_value=None)  # type: ignore[method-assign]

        count = await repo.count_by_workspace_id(uuid4())
        assert count == 0
