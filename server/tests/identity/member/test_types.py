"""Tests for ``rapidly/identity/member/types.py``.

Member is the B2B-member primitive inside a Customer. The types
carry a few contracts worth pinning:

- ``name`` is wrapped in ``MemberNameInput`` which stacks ``MaxLen(256)``
  and ``EmptyStrToNoneValidator`` — overlong names and whitespace-
  only inputs are both handled at the API boundary
- ``external_id`` on write paths runs through ``EmptyStrToNoneValidator``
  — blank strings coerce to None so the "I forgot to remove the external_id
  field" case doesn't collide with another member's real external_id
- ``MemberCreate.role`` defaults to ``MemberRole.member`` — NOT
  ``owner``. Flipping that default would silently promote every
  unspecified-role member to owner on first create.
- ``MemberUpdate`` is fully partial — both fields nullable
- Owner-at-create schema (``OwnerCreate``) has email optional (owner
  can be created without one during customer creation); ``MemberCreate``
  has email required (can't mint a member without contact info)
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from pydantic import ValidationError

from rapidly.identity.member.types import (
    MemberCreate,
    MemberUpdate,
    OwnerCreate,
)
from rapidly.models.member import MemberRole


class TestMemberNameInput:
    def test_max_256_chars(self) -> None:
        # A regression removing the length cap would let a 10 KB
        # display name hit the dashboard and break layout.
        with pytest.raises(ValidationError):
            MemberCreate(
                customer_id=uuid4(),
                email="member@example.com",
                name="a" * 257,
            )

    def test_256_char_is_accepted(self) -> None:
        body = MemberCreate(
            customer_id=uuid4(),
            email="member@example.com",
            name="a" * 256,
        )
        assert body.name == "a" * 256

    def test_whitespace_only_becomes_none(self) -> None:
        # ``EmptyStrToNoneValidator`` is stacked on MemberNameInput.
        # A caller submitting ``"   "`` must have it coerced to None,
        # not persisted as whitespace.
        body = MemberCreate(
            customer_id=uuid4(),
            email="member@example.com",
            name="   ",
        )
        assert body.name is None


class TestExternalIdCoercion:
    def test_blank_external_id_coerces_to_none(self) -> None:
        # Prevents the "forgot to remove the external_id field" case
        # where an empty submission would collide with another
        # member's real external_id.
        body = MemberCreate(
            customer_id=uuid4(),
            email="member@example.com",
            external_id="",
        )
        assert body.external_id is None

    def test_whitespace_external_id_coerces_to_none(self) -> None:
        body = MemberCreate(
            customer_id=uuid4(),
            email="member@example.com",
            external_id="   ",
        )
        assert body.external_id is None


class TestMemberCreateDefaults:
    def test_role_defaults_to_member_not_owner(self) -> None:
        # Load-bearing pin: flipping the default to ``owner`` would
        # silently promote every unspecified-role create to owner
        # — a privilege-escalation class of bug.
        body = MemberCreate(
            customer_id=uuid4(),
            email="member@example.com",
        )
        assert body.role == MemberRole.member
        # Explicit value-level comparison pins the rule at runtime
        # while sidestepping mypy's literal-type narrowing.
        assert body.role.value != MemberRole.owner.value

    def test_requires_email(self) -> None:
        # Unlike OwnerCreate, regular MemberCreate requires email —
        # you can't mint a member without contact info for role
        # handoff / password reset.
        with pytest.raises(ValidationError):
            MemberCreate.model_validate({"customer_id": str(uuid4()), "role": "member"})

    def test_requires_customer_id(self) -> None:
        with pytest.raises(ValidationError):
            MemberCreate.model_validate({"email": "member@example.com"})


class TestMemberUpdateIsPartial:
    def test_all_fields_optional(self) -> None:
        # Partial-update shape — a regression making role required
        # would break every PATCH that only changes the name.
        body = MemberUpdate()
        assert body.name is None
        assert body.role is None

    def test_rejects_unknown_role(self) -> None:
        with pytest.raises(ValidationError):
            MemberUpdate.model_validate({"role": "superuser"})


class TestOwnerCreate:
    def test_email_is_optional(self) -> None:
        # Owner can be created without email during customer-create —
        # typical when an admin provisions a customer and the owner
        # contact is added later.
        body = OwnerCreate()
        assert body.email is None
        assert body.name is None
        assert body.external_id is None

    def test_whitespace_external_id_coerces_to_none(self) -> None:
        # Same ``EmptyStrToNoneValidator`` coercion as MemberCreate.
        body = OwnerCreate(external_id="   ")
        assert body.external_id is None
