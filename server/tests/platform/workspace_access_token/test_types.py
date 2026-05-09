"""Tests for ``rapidly/platform/workspace_access_token/types.py``.

``AvailableScope`` is the security-critical filter that keeps
browser-session-only scopes (``web:read`` / ``web:write``, declared as
``RESERVED_SCOPES``) out of third-party workspace access tokens.
The module dynamically builds a ``StrEnum`` from
``[s for s in Scope if s not in RESERVED_SCOPES]`` — a regression
that dropped the filter would let a caller mint a workspace access
token carrying ``web:write`` (browser-session scope intended only
for first-party cookie auth) and skip the dashboard's CSRF posture.

Also pins the Create / Update partial-update shape and the
``token + workspace_access_token`` response envelope.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from rapidly.identity.auth.scope import RESERVED_SCOPES, Scope
from rapidly.platform.workspace_access_token.types import (
    AvailableScope,
    WorkspaceAccessTokenCreate,
    WorkspaceAccessTokenUpdate,
)


class TestAvailableScopeExcludesReserved:
    def test_reserved_scopes_are_not_in_available_scope(self) -> None:
        # Load-bearing security pin. ``web:read`` / ``web:write`` are
        # browser-session-only scopes; letting them into
        # AvailableScope would let the access-token API mint tokens
        # that hold them, bypassing the dashboard cookie posture.
        available_values = {e.value for e in AvailableScope}
        reserved_values = {s.value for s in RESERVED_SCOPES}
        assert available_values.isdisjoint(reserved_values)

    def test_every_non_reserved_scope_is_available(self) -> None:
        # The filter is inclusive on the non-reserved side — drop a
        # scope silently and dashboard-created tokens would lose that
        # capability without a visible failure.
        available_values = {e.value for e in AvailableScope}
        expected = {s.value for s in Scope if s not in RESERVED_SCOPES}
        assert available_values == expected


class TestWorkspaceAccessTokenCreate:
    def test_rejects_reserved_scope_in_scopes_list(self) -> None:
        # Even if a caller crafts the body by hand, the AvailableScope
        # StrEnum validates away the reserved values at the Pydantic
        # boundary.
        with pytest.raises(ValidationError):
            WorkspaceAccessTokenCreate.model_validate(
                {
                    "comment": "x",
                    "scopes": [Scope.web_read.value],
                }
            )

    def test_accepts_unreserved_scope(self) -> None:
        # Pick any non-reserved scope deterministically.
        first = next(iter(s for s in Scope if s not in RESERVED_SCOPES))
        body = WorkspaceAccessTokenCreate.model_validate(
            {"comment": "x", "scopes": [first.value]}
        )
        assert len(body.scopes) == 1

    def test_requires_comment(self) -> None:
        # ``comment`` is a required audit field so workspace owners
        # can tell tokens apart in the dashboard.
        with pytest.raises(ValidationError):
            WorkspaceAccessTokenCreate.model_validate({"scopes": []})

    def test_workspace_id_and_expires_in_are_optional(self) -> None:
        body = WorkspaceAccessTokenCreate.model_validate({"comment": "x", "scopes": []})
        assert body.workspace_id is None
        assert body.expires_in is None


class TestWorkspaceAccessTokenUpdate:
    def test_all_fields_optional(self) -> None:
        body = WorkspaceAccessTokenUpdate()
        assert body.comment is None
        assert body.scopes is None

    def test_update_rejects_reserved_scope(self) -> None:
        # The update path must mirror the create path — a regression
        # that only filtered scopes on create would let a caller
        # escalate an existing token by updating its scopes with
        # ``web:write``.
        with pytest.raises(ValidationError):
            WorkspaceAccessTokenUpdate.model_validate(
                {"scopes": [Scope.web_write.value]}
            )
