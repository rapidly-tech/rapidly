"""Tests for ``rapidly/identity/auth/models.py``.

Focuses on the behaviour that can be exercised without real DB models
— the ``Anonymous`` placeholder type, ``AuthPrincipal`` attribute
storage and rate-limit key derivation for the anonymous case, and the
``is_anonymous_principal`` type guard. The other type-guard functions
(``is_user_principal``, ``is_workspace_principal``, …) are exercised
through the integration tests that already exist in
``tests/identity/member/test_service.py`` and ``tests/customers/``.
"""

from __future__ import annotations

import pytest

from rapidly.enums import RateLimitGroup
from rapidly.identity.auth.models import (
    Anonymous,
    AuthPrincipal,
    is_anonymous_principal,
    is_customer_principal,
    is_member_principal,
    is_user_principal,
    is_workspace_principal,
)
from rapidly.identity.auth.scope import Scope


class TestAnonymous:
    def test_uses_empty_slots_to_prevent_attribute_assignment(self) -> None:
        # ``__slots__ = ()`` means instances have no ``__dict__`` and
        # cannot grow new attributes at runtime — prevents an attacker-
        # controlled attribute injection on this sentinel type.
        anon = Anonymous()
        with pytest.raises(AttributeError):
            anon.foo = "bar"  # type: ignore[attr-defined]

    def test_two_instances_are_equal_by_type_not_identity(self) -> None:
        # Anonymous has no state; ``isinstance`` is the only meaningful
        # identity check. Two fresh instances are distinguishable by
        # ``is`` but both resolve as the same sentinel type.
        a, b = Anonymous(), Anonymous()
        assert isinstance(a, Anonymous)
        assert isinstance(b, Anonymous)


class TestAuthPrincipalWithAnonymous:
    def test_stores_subject_scopes_and_session(self) -> None:
        anon = Anonymous()
        scopes = {Scope.openid, Scope.profile}
        principal = AuthPrincipal(anon, scopes, None)
        assert principal.subject is anon
        assert principal.scopes == scopes
        assert principal.session is None

    def test_rate_limit_user_falls_back_to_prefix_when_no_subject_id(self) -> None:
        # Anonymous has no ``id`` attribute — rate_limit_user collapses
        # to the bare prefix string.
        principal = AuthPrincipal(Anonymous(), set(), None)
        assert principal.rate_limit_user == "anonymous"

    def test_rate_limit_group_defaults_for_anonymous(self) -> None:
        # No UserSession → not ``web``; not a Workspace → no override;
        # not an OAuth2Token → falls through to ``default``.
        principal = AuthPrincipal(Anonymous(), set(), None)
        assert principal.rate_limit_group == RateLimitGroup.default

    def test_rate_limit_key_is_a_tuple_of_user_and_group(self) -> None:
        principal = AuthPrincipal(Anonymous(), set(), None)
        assert principal.rate_limit_key == (
            "anonymous",
            RateLimitGroup.default,
        )

    def test_rate_limit_key_is_cached(self) -> None:
        # ``@cached_property`` — same tuple instance across calls.
        principal = AuthPrincipal(Anonymous(), set(), None)
        a = principal.rate_limit_key
        b = principal.rate_limit_key
        assert a is b

    def test_log_context_contains_subject_type_and_rate_limit_fields(
        self,
    ) -> None:
        principal = AuthPrincipal(Anonymous(), set(), None)
        ctx = principal.log_context
        assert ctx["subject_type"] == "Anonymous"
        assert ctx["rate_limit_group"] == "default"
        assert ctx["rate_limit_user"] == "anonymous"
        # Anonymous isn't User/Workspace/Customer/Member, so no
        # subject_id in the baggage.
        assert "subject_id" not in ctx
        # No session → no session_type / is_impersonation.
        assert "session_type" not in ctx
        assert "is_impersonation" not in ctx


class TestIsAnonymousPrincipal:
    def test_true_for_anonymous_subject(self) -> None:
        principal = AuthPrincipal(Anonymous(), set(), None)
        assert is_anonymous_principal(principal) is True

    def test_false_for_non_anonymous_subject(self) -> None:
        # The other type-guard functions must all return False when the
        # subject is Anonymous — pinning that the guards are mutually
        # exclusive for this sentinel.
        principal = AuthPrincipal(Anonymous(), set(), None)
        assert is_user_principal(principal) is False
        assert is_workspace_principal(principal) is False
        assert is_customer_principal(principal) is False
        assert is_member_principal(principal) is False


class TestAuthPrincipalSlotsAndMutability:
    def test_allows_additional_attributes_via_shared_dict(self) -> None:
        # AuthPrincipal's ``__slots__`` includes ``__dict__``, which
        # means extra attrs ARE allowed (unlike Anonymous). Pinning so
        # callers that set ad-hoc context (e.g. impersonation flags)
        # keep working.
        principal = AuthPrincipal(Anonymous(), set(), None)
        principal.custom = "tag"  # type: ignore[attr-defined]
        assert principal.custom == "tag"  # type: ignore[attr-defined]
