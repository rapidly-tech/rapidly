"""Tests for ``rapidly/identity/oauth2/sub_type.py``.

Pins:
- ``SubType`` enum membership + string values
- ``is_sub_user`` / ``is_sub_workspace`` TypeGuards are mutually
  exclusive and inspect only the first tuple element

The discriminator exists to resolve an access token's ``sub`` claim
into the right entity type. A type-guard that accidentally returns
``True`` for the wrong discriminator would route a user token's
permissions through the workspace code path — a cross-subject
privilege-escalation bug.
"""

from __future__ import annotations

from rapidly.identity.oauth2.sub_type import (
    SubType,
    is_sub_user,
    is_sub_workspace,
)


class TestSubType:
    def test_exposes_exactly_user_and_workspace(self) -> None:
        # ``public`` / ``pairwise`` are OIDC discovery values — those
        # are a separate axis. This enum is the internal user-vs-
        # workspace discriminator.
        assert {s.value for s in SubType} == {"user", "workspace"}

    def test_is_str_enum_for_direct_comparison(self) -> None:
        # StrEnum — ``sub_type == 'user'`` works in raw SQL / JSON.
        assert str(SubType.user) == "user"
        assert str(SubType.workspace) == "workspace"

    def test_exactly_two_members(self) -> None:
        # Adding a third SubType would require updating
        # ``ACCESS_TOKEN_PREFIX`` + ``REFRESH_TOKEN_PREFIX`` dicts
        # plus every ``sub`` hybrid-property in the ORM. Pinned so
        # that work is forced through an explicit PR.
        assert len(list(SubType)) == 2


class TestIsSubUser:
    def test_true_for_user_discriminator(self) -> None:
        # ``is_sub_user`` checks only the first tuple element. We pass
        # a sentinel object as the second element since the guard
        # doesn't inspect it — documenting that the type narrowing is
        # discriminator-only, not identity-based.
        sentinel = object()
        assert is_sub_user((SubType.user, sentinel)) is True  # type: ignore[arg-type]

    def test_false_for_workspace_discriminator(self) -> None:
        sentinel = object()
        assert is_sub_user((SubType.workspace, sentinel)) is False  # type: ignore[arg-type]


class TestIsSubWorkspace:
    def test_true_for_workspace_discriminator(self) -> None:
        sentinel = object()
        assert is_sub_workspace((SubType.workspace, sentinel)) is True  # type: ignore[arg-type]

    def test_false_for_user_discriminator(self) -> None:
        sentinel = object()
        assert is_sub_workspace((SubType.user, sentinel)) is False  # type: ignore[arg-type]


class TestGuardsAreMutuallyExclusive:
    def test_user_tuple_only_passes_is_sub_user(self) -> None:
        # Security invariant: for any SubTypeValue, exactly one guard
        # returns True. Pinning prevents an accidental fallthrough
        # where both guards pass (would be a cross-subject bug).
        sentinel = object()
        tup = (SubType.user, sentinel)
        assert is_sub_user(tup) is True  # type: ignore[arg-type]
        assert is_sub_workspace(tup) is False  # type: ignore[arg-type]

    def test_workspace_tuple_only_passes_is_sub_workspace(self) -> None:
        sentinel = object()
        tup = (SubType.workspace, sentinel)
        assert is_sub_user(tup) is False  # type: ignore[arg-type]
        assert is_sub_workspace(tup) is True  # type: ignore[arg-type]
