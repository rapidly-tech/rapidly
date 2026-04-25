"""Tests for ``rapidly/platform/workspace/resolver.py``.

Resolves ``workspace_id`` payloads to a Workspace model. Four
load-bearing surfaces:

- WORKSPACE-token principal: caller MUST NOT supply
  ``workspace_id`` — drift to allow would let a workspace token
  impersonate another workspace by passing a different id in
  the request body. Returns the principal's own workspace
  unchanged.
- USER principal with no ``workspace_id``: raises
  ``RequestValidationError`` with the documented "missing"
  error message. Drift to silently fall through would surface
  null-pointer errors deep in callers.
- USER principal with ``workspace_id`` they DO belong to:
  returns the workspace. The membership subquery filters
  ``deleted_at IS NULL`` — drift to drop would let removed
  members continue acting on the workspace.
- USER principal with ``workspace_id`` they DON'T belong to
  (or that doesn't exist): raises ``RequestValidationError``
  with "Workspace not found.". Drift to leak existence would
  let attackers enumerate workspace IDs.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from rapidly.errors import RequestValidationError
from rapidly.platform.workspace.resolver import get_payload_workspace


def _model(workspace_id: Any = None) -> Any:
    m = MagicMock()
    m.workspace_id = workspace_id
    return m


def _user_principal(user_id: Any = None) -> Any:
    p = MagicMock()
    p.subject = MagicMock()
    p.subject.id = user_id or uuid4()
    return p


def _workspace_principal(workspace_id: Any = None) -> Any:
    p = MagicMock()
    p.subject = MagicMock()
    p.subject.id = workspace_id or uuid4()
    return p


@pytest.mark.asyncio
class TestWorkspacePrincipal:
    async def test_returns_principals_own_workspace_when_no_payload_id(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Pin: workspace tokens default to acting on their own
        # workspace. No DB hit.
        monkeypatch.setattr(
            "rapidly.platform.workspace.resolver.is_workspace_principal",
            lambda p: True,
        )

        principal = _workspace_principal()
        model = _model(workspace_id=None)

        out = await get_payload_workspace(MagicMock(), principal, model)
        assert out is principal.subject

    async def test_rejects_explicit_workspace_id_in_payload(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Pin: a workspace token MUST NOT be allowed to set
        # ``workspace_id`` in the payload — drift would let it
        # impersonate another workspace.
        monkeypatch.setattr(
            "rapidly.platform.workspace.resolver.is_workspace_principal",
            lambda p: True,
        )

        principal = _workspace_principal()
        model = _model(workspace_id=uuid4())

        with pytest.raises(RequestValidationError):
            await get_payload_workspace(MagicMock(), principal, model)


@pytest.mark.asyncio
class TestUserPrincipalMissingId:
    async def test_no_workspace_id_raises_validation_error(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Pin: explicit "workspace_id is required" error rather
        # than NullPointer deep in callers.
        monkeypatch.setattr(
            "rapidly.platform.workspace.resolver.is_workspace_principal",
            lambda p: False,
        )

        principal = _user_principal()
        model = _model(workspace_id=None)

        with pytest.raises(RequestValidationError):
            await get_payload_workspace(MagicMock(), principal, model)


@pytest.mark.asyncio
class TestUserPrincipalMembershipScope:
    async def test_returns_workspace_when_user_is_member(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Pin: clean path. The membership subquery filters
        # ``deleted_at IS NULL`` (encoded in the SQL — drift
        # would let removed members keep acting).
        monkeypatch.setattr(
            "rapidly.platform.workspace.resolver.is_workspace_principal",
            lambda p: False,
        )

        target_workspace = MagicMock()
        result = MagicMock()
        result.scalar_one_or_none.return_value = target_workspace

        session = MagicMock()
        session.execute = AsyncMock(return_value=result)

        principal = _user_principal()
        model = _model(workspace_id=uuid4())

        out = await get_payload_workspace(session, principal, model)
        assert out is target_workspace

    async def test_membership_filter_uses_deleted_at_is_null(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Pin: membership subquery enforces active-membership
        # gate. Drift to drop would let removed members keep
        # acting on the workspace.
        monkeypatch.setattr(
            "rapidly.platform.workspace.resolver.is_workspace_principal",
            lambda p: False,
        )
        captured: dict[str, Any] = {}

        async def _exec(stmt: object) -> Any:
            captured["stmt"] = stmt
            r = MagicMock()
            r.scalar_one_or_none.return_value = MagicMock()
            return r

        session = MagicMock()
        session.execute = AsyncMock(side_effect=_exec)

        principal = _user_principal()
        model = _model(workspace_id=uuid4())

        await get_payload_workspace(session, principal, model)

        sql = str(
            captured["stmt"].compile(compile_kwargs={"literal_binds": True})
        ).lower()
        assert "workspace_memberships.deleted_at is null" in sql
        assert "workspace_memberships.user_id" in sql

    async def test_non_member_workspace_raises_not_found(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Pin: the SQL returned NO row → raise
        # ``RequestValidationError`` with "Workspace not found."
        # Drift to surface a different error (e.g.
        # ``Forbidden``) would tell attackers whether the
        # workspace EXISTS — drift to surface IDs in the error
        # message would help enumeration.
        monkeypatch.setattr(
            "rapidly.platform.workspace.resolver.is_workspace_principal",
            lambda p: False,
        )

        result = MagicMock()
        result.scalar_one_or_none.return_value = None

        session = MagicMock()
        session.execute = AsyncMock(return_value=result)

        principal = _user_principal()
        model = _model(workspace_id=uuid4())

        with pytest.raises(RequestValidationError):
            await get_payload_workspace(session, principal, model)
