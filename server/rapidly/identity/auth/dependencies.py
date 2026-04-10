"""Authentication dependency injection for FastAPI routes.

The public entry point is ``Authenticator()``, which returns a callable
dependency that:

1. Checks that the request's subject matches the endpoint's allow-list.
2. Verifies that the caller holds at least one of the required scopes.

The generated dependency dynamically adjusts its FastAPI ``Security``
signature so that the OpenAPI spec lists only the relevant security
schemes for each endpoint.
"""

from collections.abc import Awaitable, Callable
from inspect import Parameter, Signature
from typing import Annotated, Any

from fastapi import Depends, Request, Security
from fastapi.security import HTTPBearer, OpenIdConnect
from makefun import with_signature

from rapidly.errors import Unauthorized
from rapidly.identity.auth.scope import RESERVED_SCOPES, Scope
from rapidly.identity.oauth2.exceptions import InsufficientScopeError

from .models import (
    Anonymous,
    AuthPrincipal,
    Customer,
    Member,
    Subject,
    SubjectType,
    User,
    Workspace,
    is_anonymous_principal,
)

# ---------------------------------------------------------------------------
# Security scheme declarations
# ---------------------------------------------------------------------------

oidc_scheme = OpenIdConnect(
    scheme_name="oidc",
    openIdConnectUrl="/.well-known/openid-configuration",
    auto_error=False,
)
oat_scheme = HTTPBearer(
    scheme_name="oat",
    auto_error=False,
    description="Create an **Workspace Access Token** in your workspace's settings page.",
)
customer_session_scheme = HTTPBearer(
    scheme_name="customer_session",
    auto_error=False,
    description=(
        "Customer session tokens authenticate end-users in the customer portal. "
        "Create them via the "
        "[Create Customer Session endpoint](/api-reference/customer-portal/sessions/create)."
    ),
)
member_session_scheme = HTTPBearer(
    scheme_name="member_session",
    auto_error=False,
    description=(
        "Member session tokens authenticate team members in the member portal. "
        "Create them via the "
        "[Create Member Session endpoint](/api-reference/member-portal/sessions/create)."
    ),
)


# ---------------------------------------------------------------------------
# Auth-subject factory (dynamically builds a FastAPI dependency whose
# signature references only the security schemes that the endpoint needs)
# ---------------------------------------------------------------------------

# Subject type -> (parameter name, scheme dependency)
_SUBJECT_SCHEME_MAP: list[tuple[frozenset[type], str, Any]] = [
    (frozenset({User, Workspace}), "oauth2_credentials", Depends(oidc_scheme)),
    (frozenset({Workspace}), "workspace_access_token_credentials", Depends(oat_scheme)),
    (
        frozenset({Customer}),
        "customer_session_credentials",
        Depends(customer_session_scheme),
    ),
    (frozenset({Member}), "member_session_credentials", Depends(member_session_scheme)),
]

_factory_cache: dict[
    frozenset[SubjectType], Callable[..., Awaitable[AuthPrincipal[Subject]]]
] = {}


def _get_auth_subject_factory(
    allowed: frozenset[SubjectType],
) -> Callable[..., Awaitable[AuthPrincipal[Subject]]]:
    """Build (and cache) an async factory whose FastAPI signature declares
    only the security schemes relevant to *allowed*.
    """
    if allowed in _factory_cache:
        return _factory_cache[allowed]

    params: list[Parameter] = [
        Parameter("request", Parameter.POSITIONAL_OR_KEYWORD, annotation=Request),
    ]
    for subject_types, param_name, default in _SUBJECT_SCHEME_MAP:
        if subject_types & allowed:
            params.append(
                Parameter(param_name, Parameter.KEYWORD_ONLY, default=default)
            )

    @with_signature(Signature(params))
    async def _factory(request: Request, **_kw: Any) -> AuthPrincipal[Subject]:
        try:
            return request.state.auth_subject
        except AttributeError as exc:
            raise RuntimeError(
                "AuthPrincipal is not present in the request state. "
                "Did you forget to add AuthPrincipalMiddleware?"
            ) from exc

    _factory_cache[allowed] = _factory
    return _factory


# ---------------------------------------------------------------------------
# Authenticator
# ---------------------------------------------------------------------------


class _Authenticator:
    """Validates subject type and scope requirements at request time."""

    __slots__ = ("allowed_subjects", "required_scopes")

    def __init__(
        self,
        *,
        allowed_subjects: frozenset[SubjectType],
        required_scopes: set[Scope] | None = None,
    ) -> None:
        self.allowed_subjects = allowed_subjects
        self.required_scopes = required_scopes

    async def __call__(
        self, auth_subject: AuthPrincipal[Subject]
    ) -> AuthPrincipal[Subject]:
        # Replace disallowed subject types with Anonymous
        if type(auth_subject.subject) not in self.allowed_subjects:
            auth_subject = AuthPrincipal(Anonymous(), set(), None)

        if is_anonymous_principal(auth_subject):
            if Anonymous in self.allowed_subjects:
                return auth_subject
            raise Unauthorized()

        # Scope check: caller must hold at least one required scope
        if self.required_scopes and not (auth_subject.scopes & self.required_scopes):
            raise InsufficientScopeError(set(self.required_scopes))

        return auth_subject


def Authenticator(
    allowed_subjects: set[SubjectType],
    required_scopes: set[Scope] | None = None,
) -> _Authenticator:
    """Build an ``_Authenticator`` whose ``__call__`` signature exposes
    the correct ``Security`` dependencies for the OpenAPI spec.

    ``required_scopes`` uses **any-of** semantics: the caller must hold
    *at least one* of the listed scopes (set intersection), not all of
    them.  This allows listing read *and* write scopes so that a token
    with either can access the endpoint.
    """
    frozen = frozenset(allowed_subjects)

    # Compute the public scope values for OpenAPI (exclude internal scopes)
    visible_scopes = sorted(
        s.value for s in (required_scopes or set()) if s not in RESERVED_SCOPES
    )

    call_params = [
        Parameter("self", Parameter.POSITIONAL_OR_KEYWORD),
        Parameter(
            "auth_subject",
            Parameter.POSITIONAL_OR_KEYWORD,
            default=Security(_get_auth_subject_factory(frozen), scopes=visible_scopes),
        ),
    ]

    class _Bound(_Authenticator):
        @with_signature(Signature(call_params))
        async def __call__(
            self, auth_subject: AuthPrincipal[Subject]
        ) -> AuthPrincipal[Subject]:
            return await super().__call__(auth_subject)

    return _Bound(allowed_subjects=frozen, required_scopes=required_scopes)


# ---------------------------------------------------------------------------
# Pre-built dependency aliases used across the codebase
# ---------------------------------------------------------------------------

_WebUserOrAnonymous = Authenticator(
    allowed_subjects={Anonymous, User},
    required_scopes={Scope.web_write},
)
WebUserOrAnonymous = Annotated[
    AuthPrincipal[Anonymous | User], Depends(_WebUserOrAnonymous)
]

_WebUserRead = Authenticator(
    allowed_subjects={User}, required_scopes={Scope.web_read, Scope.web_write}
)
WebUserRead = Annotated[AuthPrincipal[User], Depends(_WebUserRead)]

_WebUserWrite = Authenticator(
    allowed_subjects={User}, required_scopes={Scope.web_write}
)
WebUserWrite = Annotated[AuthPrincipal[User], Depends(_WebUserWrite)]
