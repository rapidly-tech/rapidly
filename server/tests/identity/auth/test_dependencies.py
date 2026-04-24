"""Tests for ``rapidly/identity/auth/dependencies.py``.

``_Authenticator`` is the load-bearing auth check that runs on every
authenticated endpoint. Two decisions must stay correct:

1. **Subject-type allow-list**: requests arriving with a subject
   outside ``allowed_subjects`` get their credentials stripped (the
   principal is coerced to ``Anonymous``). This is critical — a
   regression that kept the original subject in place would let an
   authenticated Customer hit a User-only endpoint carrying the
   Customer's session token.
2. **Scope any-of check**: the required-scopes set uses OR semantics
   (caller needs ONE of the listed scopes). A regression flipping
   to AND would break every endpoint that lists both a read and a
   write scope (so either scope can access the endpoint).

Also pins the ``Anonymous``-in-allow-list branch (pre-auth endpoints
like ``LoginCodeRequest``) and the pre-built ``WebUser*`` aliases
that every browser-facing route uses.
"""

from __future__ import annotations

from typing import Any

import pytest
from fastapi.params import Depends

from rapidly.errors import Unauthorized
from rapidly.identity.auth.dependencies import (
    Authenticator,
    WebUserOrAnonymous,
    WebUserRead,
    WebUserWrite,
    _Authenticator,
)
from rapidly.identity.auth.models import (
    Anonymous,
    AuthPrincipal,
    User,
    Workspace,
)
from rapidly.identity.auth.scope import Scope
from rapidly.identity.oauth2.exceptions import InsufficientScopeError


def _principal(subject_cls: Any, scopes: set[Scope] | None = None) -> AuthPrincipal:  # type: ignore[type-arg]
    """Construct a minimal AuthPrincipal whose ``type(subject)`` equals
    the given class — ``_Authenticator`` checks ``type(...) not in
    allowed_subjects``, so ``MagicMock(spec=X)`` won't satisfy it.
    ``cls.__new__`` bypasses the SQLAlchemy / dataclass ctor."""
    subject = subject_cls.__new__(subject_cls)
    return AuthPrincipal(subject, scopes or set(), None)


def _anonymous() -> AuthPrincipal:  # type: ignore[type-arg]
    return AuthPrincipal(Anonymous(), set(), None)


@pytest.mark.asyncio
class TestAuthenticatorSubjectCheck:
    async def test_allowed_subject_with_matching_scope_passes(self) -> None:
        auth = _Authenticator(
            allowed_subjects=frozenset({User}),
            required_scopes={Scope.web_read},
        )
        principal = _principal(User, {Scope.web_read})
        result = await auth(principal)
        assert result is principal

    async def test_disallowed_subject_falls_back_to_anonymous(self) -> None:
        # Load-bearing pin: a Workspace-subject request hitting a
        # User-only endpoint gets its credentials stripped (principal
        # becomes Anonymous) BEFORE the scope check. Without this,
        # the Workspace's scopes would leak into the authorization
        # decision on an endpoint that shouldn't accept them.
        auth = _Authenticator(
            allowed_subjects=frozenset({User}),
            required_scopes={Scope.web_read},
        )
        principal = _principal(Workspace, {Scope.web_read})
        with pytest.raises(Unauthorized):
            await auth(principal)


@pytest.mark.asyncio
class TestAuthenticatorAnonymous:
    async def test_anonymous_rejected_when_not_allowed(self) -> None:
        auth = _Authenticator(
            allowed_subjects=frozenset({User}),
            required_scopes={Scope.web_read},
        )
        with pytest.raises(Unauthorized):
            await auth(_anonymous())

    async def test_anonymous_accepted_when_in_allowed_set(self) -> None:
        # Pre-auth endpoints (LoginCodeRequest, public storefront
        # reads) allow Anonymous — the check must short-circuit
        # BEFORE requiring any scopes.
        auth = _Authenticator(
            allowed_subjects=frozenset({Anonymous, User}),
            required_scopes={Scope.web_read},
        )
        result = await auth(_anonymous())
        assert isinstance(result.subject, Anonymous)


@pytest.mark.asyncio
class TestAuthenticatorScopeCheck:
    async def test_missing_scope_raises_insufficient_scope(self) -> None:
        # Load-bearing: InsufficientScopeError → 403 (not 401) —
        # client has valid credentials but wrong permissions.
        auth = _Authenticator(
            allowed_subjects=frozenset({User}),
            required_scopes={Scope.web_write},
        )
        principal = _principal(User, {Scope.web_read})
        with pytest.raises(InsufficientScopeError):
            await auth(principal)

    async def test_any_of_scope_semantics(self) -> None:
        # Required scopes are ANY-of (set intersection must be
        # non-empty). A regression to ALL-of would break every
        # endpoint that lists ``{read, write}`` to accept either.
        auth = _Authenticator(
            allowed_subjects=frozenset({User}),
            required_scopes={Scope.web_read, Scope.web_write},
        )
        # Holds only ONE of the required scopes — must pass.
        principal = _principal(User, {Scope.web_read})
        result = await auth(principal)
        assert result is principal

    async def test_no_required_scopes_passes_any_scope_set(self) -> None:
        # An endpoint with required_scopes=None accepts any
        # authenticated subject regardless of scopes (e.g. a
        # "who am I" endpoint).
        auth = _Authenticator(
            allowed_subjects=frozenset({User}),
            required_scopes=None,
        )
        principal = _principal(User, set())
        result = await auth(principal)
        assert result is principal


class TestPreBuiltAliases:
    def _extract(self, annotated_type: object) -> _Authenticator:
        meta = annotated_type.__metadata__  # type: ignore[attr-defined]
        dep = meta[0]
        assert isinstance(dep, Depends)
        auth = dep.dependency
        assert isinstance(auth, _Authenticator)
        return auth

    def test_web_user_or_anonymous_shape(self) -> None:
        auth = self._extract(WebUserOrAnonymous)
        assert auth.allowed_subjects == frozenset({Anonymous, User})
        assert auth.required_scopes == {Scope.web_write}

    def test_web_user_read_allows_both_web_scopes(self) -> None:
        # Read-only endpoints accept either web:read OR web:write —
        # a browser session with web:write can still GET data.
        auth = self._extract(WebUserRead)
        assert auth.allowed_subjects == frozenset({User})
        assert auth.required_scopes == {Scope.web_read, Scope.web_write}

    def test_web_user_write_requires_web_write_only(self) -> None:
        # Write endpoints need the write scope specifically — a
        # read-only session must not be able to mutate.
        auth = self._extract(WebUserWrite)
        assert auth.allowed_subjects == frozenset({User})
        assert auth.required_scopes == {Scope.web_write}


class TestAuthenticatorConstructorCaching:
    def test_returns_authenticator_instance(self) -> None:
        # ``Authenticator(...)`` is the dynamic signature-adjusted
        # constructor; pinning the return type so a refactor that
        # changed it would surface here.
        instance = Authenticator(
            allowed_subjects={User}, required_scopes={Scope.web_read}
        )
        assert isinstance(instance, _Authenticator)
        assert instance.allowed_subjects == frozenset({User})
        assert instance.required_scopes == {Scope.web_read}
