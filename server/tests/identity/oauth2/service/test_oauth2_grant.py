"""Tests for ``rapidly/identity/oauth2/actions/oauth2_grant.py``.

Consent grant persistence. Three load-bearing surfaces:

- ``_apply_sub_filter`` routes to the correct FK column
  (user_id vs workspace_id) based on ``sub_type``. Drift would
  let a user-scoped grant be queried via the workspace_id
  column and silently return zero rows (forced re-consent on
  every request).
- ``create_or_update_grant`` is an UPSERT: existing grants get
  their scope REPLACED; new grants get the FK set on the
  appropriate column. Drift to additive scope-merge would let
  a previously-revoked scope sneak back in. Drift in FK
  routing would write to the wrong subject column.
- ``has_granted_scope`` returns True iff EVERY requested scope
  is in the grant's stored scope list (subset check). Whitespace-
  split per RFC 6749 §3.3. Drift to substring-match would let
  a malicious scope ``read_x`` slip through when the user
  granted ``read_y``.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from rapidly.identity.oauth2.actions.oauth2_grant import (
    OAuth2GrantService,
    _apply_sub_filter,
    oauth2_grant,
)
from rapidly.identity.oauth2.sub_type import SubType


def _session_with_grant(existing: Any | None) -> MagicMock:
    """Build a session whose execute() returns *existing* via scalar_one_or_none."""
    session = MagicMock()
    result = MagicMock()
    result.unique = MagicMock(return_value=result)
    result.scalar_one_or_none = MagicMock(return_value=existing)
    session.execute = MagicMock(return_value=result)
    return session


class TestApplySubFilter:
    def test_user_branch(self) -> None:
        # Pin: user sub_type narrows by user_id. Drift would
        # silently miss the grant and force re-consent.
        sid = uuid4()
        stmt = MagicMock()
        result = _apply_sub_filter(stmt, SubType.user, sid)
        # Pin: ``stmt.where(...)`` was called once. The exact
        # SQLAlchemy column comparison is opaque to mock.
        stmt.where.assert_called_once()
        assert result is stmt.where.return_value

    def test_workspace_branch(self) -> None:
        sid = uuid4()
        stmt = MagicMock()
        _apply_sub_filter(stmt, SubType.workspace, sid)
        stmt.where.assert_called_once()

    def test_unknown_sub_type_raises(self) -> None:
        # Pin: an unknown sub_type raises NotImplementedError
        # loudly. Drift to silently return the unfiltered
        # statement would leak ALL consent records.
        with pytest.raises(NotImplementedError, match="Unsupported sub_type"):
            _apply_sub_filter(MagicMock(), "weird", uuid4())  # type: ignore[arg-type]


class TestCreateOrUpdateGrant:
    def test_existing_grant_scope_replaced(self) -> None:
        # Pin: existing grant gets scope REPLACED (not merged).
        # Drift to additive merge would let a previously-revoked
        # scope sneak back in via a subsequent narrow request.
        existing = MagicMock()
        existing.scope = "openid email"
        session = _session_with_grant(existing)

        result = oauth2_grant.create_or_update_grant(
            session,
            sub_type=SubType.user,
            sub_id=uuid4(),
            client_id="cli",
            scope="openid",
        )
        # The new scope replaces the old.
        assert existing.scope == "openid"
        # Returned object IS the existing grant (NOT a new one).
        assert result is existing
        session.add.assert_called_once_with(existing)
        session.flush.assert_called_once()

    def test_new_grant_user_subtype_sets_user_id(self) -> None:
        # Pin: when no grant exists for the (subject, client) pair,
        # a new OAuth2Grant is created with user_id set (NOT
        # workspace_id). Drift in FK routing would create a row
        # that doesn't match the subject's lookup.
        session = _session_with_grant(None)
        captured: list[Any] = []
        session.add = MagicMock(side_effect=captured.append)

        sid = uuid4()
        result = oauth2_grant.create_or_update_grant(
            session,
            sub_type=SubType.user,
            sub_id=sid,
            client_id="cli",
            scope="openid",
        )
        assert result.client_id == "cli"
        assert result.scope == "openid"
        assert result.user_id == sid
        # workspace_id should NOT be set on a user grant.
        assert getattr(result, "workspace_id", None) is None

    def test_new_grant_workspace_subtype_sets_workspace_id(self) -> None:
        # Pin: workspace sub_type writes to workspace_id (NOT
        # user_id). Cross-tenant data risk if reversed.
        session = _session_with_grant(None)
        captured: list[Any] = []
        session.add = MagicMock(side_effect=captured.append)

        sid = uuid4()
        result = oauth2_grant.create_or_update_grant(
            session,
            sub_type=SubType.workspace,
            sub_id=sid,
            client_id="cli",
            scope="openid",
        )
        assert result.workspace_id == sid
        assert getattr(result, "user_id", None) is None

    def test_new_grant_unknown_sub_type_raises(self) -> None:
        # Pin: unknown sub_type on the create-path raises
        # NotImplementedError. Drift to silently skip the FK
        # write would create a dangling grant row.
        session = _session_with_grant(None)
        with pytest.raises(NotImplementedError):
            oauth2_grant.create_or_update_grant(
                session,
                sub_type="weird",  # type: ignore[arg-type]
                sub_id=uuid4(),
                client_id="cli",
                scope="openid",
            )


class TestHasGrantedScope:
    def test_returns_false_when_no_grant(self) -> None:
        # Pin: missing grant → False. Defends against a regression
        # that returned True on missing grants (would force-grant
        # every scope on first encounter).
        session = _session_with_grant(None)
        result = oauth2_grant.has_granted_scope(
            session,
            sub_type=SubType.user,
            sub_id=uuid4(),
            client_id="cli",
            scope="openid",
        )
        assert result is False

    def test_subset_returns_true(self) -> None:
        # Pin: requested scope ⊆ granted → True. Enables silent
        # re-authorization when a client requests a narrower
        # scope than previously consented.
        existing = MagicMock()
        existing.scopes = {"openid", "email", "profile"}
        session = _session_with_grant(existing)
        result = oauth2_grant.has_granted_scope(
            session,
            sub_type=SubType.user,
            sub_id=uuid4(),
            client_id="cli",
            scope="openid email",
        )
        assert result is True

    def test_superset_returns_false(self) -> None:
        # LOAD-BEARING SECURITY: if the request asks for ANY scope
        # not previously granted, return False (re-consent
        # required). Drift would let a client expand its scope
        # without user re-approval.
        existing = MagicMock()
        existing.scopes = {"openid"}
        session = _session_with_grant(existing)
        result = oauth2_grant.has_granted_scope(
            session,
            sub_type=SubType.user,
            sub_id=uuid4(),
            client_id="cli",
            scope="openid email",
        )
        assert result is False

    def test_scope_split_on_whitespace(self) -> None:
        # Pin: scope strings are space-delimited per RFC 6749 §3.3.
        # Drift to comma-split or other separator would make
        # legitimate multi-scope requests look like a single
        # weird scope and silently fail the subset check.
        existing = MagicMock()
        existing.scopes = {"openid", "email"}
        session = _session_with_grant(existing)
        result = oauth2_grant.has_granted_scope(
            session,
            sub_type=SubType.user,
            sub_id=uuid4(),
            client_id="cli",
            scope="  openid   email  ",
        )
        # Pin: extra whitespace is tolerated (split() handles it).
        assert result is True

    def test_substring_does_not_match(self) -> None:
        # Pin (security): subset check is on EXACT scope tokens,
        # NOT substring-match. Otherwise a request for ``read_x``
        # would match a grant for ``read_xyz``.
        existing = MagicMock()
        existing.scopes = {"read_xyz"}
        session = _session_with_grant(existing)
        result = oauth2_grant.has_granted_scope(
            session,
            sub_type=SubType.user,
            sub_id=uuid4(),
            client_id="cli",
            scope="read_x",
        )
        assert result is False


class TestModuleSingleton:
    def test_oauth2_grant_singleton_exposed(self) -> None:
        # Pin: callers import ``oauth2_grant`` directly. Drift to
        # a different name would break every importer.
        assert isinstance(oauth2_grant, OAuth2GrantService)
