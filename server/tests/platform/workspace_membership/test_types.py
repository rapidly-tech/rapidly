"""Tests for ``rapidly/platform/workspace_membership/types.py``.

``WorkspaceMember`` flattens a nested ``user`` relation into top-level
fields via ``AliasPath("user", "id")``. The shape carries two load-
bearing contracts:

- The ``user.<field>`` alias paths — the response shape consumers
  (dashboard, TS client) read ``user_id`` / ``email`` / ``avatar_url``
  at the top level. A regression that dropped the alias path
  would leave the response fields empty/missing.
- ``is_admin`` defaults to False — a silent flip to True would
  promote every workspace membership to admin on default
  construction (privilege-escalation).
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError

from rapidly.platform.workspace_membership.types import (
    WorkspaceMember,
    WorkspaceMemberInvite,
)


class TestWorkspaceMemberAliasPath:
    def test_flattens_user_fields_via_alias_path(self) -> None:
        # The validation_alias path is ``user.id`` / ``user.email`` /
        # ``user.avatar_url``. A regression that dropped the alias
        # would map the fields to top-level ``id`` / ``email``,
        # which ORM rows don't expose directly.
        uid = uuid4()
        body = WorkspaceMember.model_validate(
            {
                "user": {
                    "id": str(uid),
                    "email": "alice@test.com",
                    "avatar_url": "https://img.example/a.png",
                },
                "created_at": datetime.now(UTC).isoformat(),
            }
        )
        assert body.user_id == uid
        assert body.email == "alice@test.com"
        assert body.avatar_url == "https://img.example/a.png"

    def test_avatar_url_is_nullable(self) -> None:
        body = WorkspaceMember.model_validate(
            {
                "user": {
                    "id": str(uuid4()),
                    "email": "alice@test.com",
                    "avatar_url": None,
                },
                "created_at": datetime.now(UTC).isoformat(),
            }
        )
        assert body.avatar_url is None


class TestIsAdminDefault:
    def test_defaults_to_false(self) -> None:
        # Load-bearing privilege-escalation defence. Workspace
        # memberships are created en-masse (one per invite
        # acceptance); the default MUST NOT be True.
        body = WorkspaceMember.model_validate(
            {
                "user": {
                    "id": str(uuid4()),
                    "email": "alice@test.com",
                    "avatar_url": None,
                },
                "created_at": datetime.now(UTC).isoformat(),
            }
        )
        assert body.is_admin is False


class TestWorkspaceMemberInvite:
    def test_requires_email(self) -> None:
        with pytest.raises(ValidationError):
            WorkspaceMemberInvite.model_validate({})

    def test_rejects_malformed_email(self) -> None:
        with pytest.raises(ValidationError):
            WorkspaceMemberInvite(email="not-an-email")

    def test_accepts_valid_email(self) -> None:
        body = WorkspaceMemberInvite(email="new@test.com")
        assert body.email == "new@test.com"
