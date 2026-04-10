"""Customer-portal auth dependencies: scope-checked authenticators.

Pre-built ``Depends`` aliases that enforce customer or member
authentication with the appropriate ``customer_portal:read`` or
``customer_portal:write`` scope.
"""

from typing import Annotated

from fastapi import Depends

from rapidly.errors import NotPermitted
from rapidly.identity.auth.dependencies import Authenticator
from rapidly.identity.auth.models import Anonymous, AuthPrincipal, Customer, Member
from rapidly.identity.auth.scope import Scope
from rapidly.models.member import MemberRole

# ── Dependencies ──

# Customer-only authenticators (legacy, for non-migrated orgs)
_CustomerPortalRead = Authenticator(
    required_scopes={
        Scope.customer_portal_read,
        Scope.customer_portal_write,
    },
    allowed_subjects={Customer},
)
CustomerPortalRead = Annotated[AuthPrincipal[Customer], Depends(_CustomerPortalRead)]

_CustomerPortalWrite = Authenticator(
    required_scopes={Scope.customer_portal_write},
    allowed_subjects={Customer},
)
CustomerPortalWrite = Annotated[AuthPrincipal[Customer], Depends(_CustomerPortalWrite)]

_CustomerPortalOAuthAccount = Authenticator(
    required_scopes={Scope.customer_portal_write},
    allowed_subjects={Customer, Member, Anonymous},
)
CustomerPortalOAuthAccount = Annotated[
    AuthPrincipal[Customer | Member | Anonymous], Depends(_CustomerPortalOAuthAccount)
]


# Member-only authenticators (for orgs with member_model_enabled=true)
_CustomerPortalMemberRead = Authenticator(
    required_scopes={
        Scope.customer_portal_read,
        Scope.customer_portal_write,
    },
    allowed_subjects={Member},
)
CustomerPortalMemberRead = Annotated[
    AuthPrincipal[Member], Depends(_CustomerPortalMemberRead)
]

_CustomerPortalMemberWrite = Authenticator(
    required_scopes={Scope.customer_portal_write},
    allowed_subjects={Member},
)
CustomerPortalMemberWrite = Annotated[
    AuthPrincipal[Member], Depends(_CustomerPortalMemberWrite)
]


# ── Permission Checks ──


class _RoleCheck:
    """Dependency that checks if a Member has one of the allowed roles."""

    def __init__(self, allowed_roles: set[MemberRole]) -> None:
        self.allowed_roles = allowed_roles

    async def __call__(
        self, auth_subject: AuthPrincipal[Member] = Depends(_CustomerPortalMemberWrite)
    ) -> AuthPrincipal[Member]:
        if auth_subject.subject.role not in self.allowed_roles:
            raise NotPermitted("Insufficient role for this operation")
        return auth_subject


# Role-based authenticators (Member-only, with role restrictions)
CustomerPortalOwner = Annotated[
    AuthPrincipal[Member],
    Depends(_RoleCheck(allowed_roles={MemberRole.owner})),
]

CustomerPortalBillingManager = Annotated[
    AuthPrincipal[Member],
    Depends(_RoleCheck(allowed_roles={MemberRole.owner, MemberRole.billing_manager})),
]


# Union authenticators (accept both Customer and Member during migration)
_CustomerPortalUnionRead = Authenticator(
    required_scopes={
        Scope.customer_portal_read,
        Scope.customer_portal_write,
    },
    allowed_subjects={Customer, Member},
)
CustomerPortalUnionRead = Annotated[
    AuthPrincipal[Customer | Member], Depends(_CustomerPortalUnionRead)
]

_CustomerPortalUnionWrite = Authenticator(
    required_scopes={Scope.customer_portal_write},
    allowed_subjects={Customer, Member},
)
CustomerPortalUnionWrite = Annotated[
    AuthPrincipal[Customer | Member], Depends(_CustomerPortalUnionWrite)
]


# Union billing authenticators (Customer always allowed, Member needs billing role)
_union_billing_roles = {MemberRole.owner, MemberRole.billing_manager}


class _UnionBillingRoleCheck:
    """Dependency that accepts Customer (always allowed) or Member with billing roles."""

    def __init__(self, allowed_roles: set[MemberRole]) -> None:
        self.allowed_roles = allowed_roles

    def _check_billing_permission(
        self, auth_subject: AuthPrincipal[Customer | Member]
    ) -> AuthPrincipal[Customer | Member]:
        """Shared permission checking logic for billing access."""
        # Customers always have billing access (legacy behavior)
        if isinstance(auth_subject.subject, Customer):
            return auth_subject
        # Members must have billing role
        if isinstance(auth_subject.subject, Member):
            if auth_subject.subject.role not in self.allowed_roles:
                raise NotPermitted(
                    "Only owners and billing managers can access billing features."
                )
            return auth_subject
        raise NotPermitted("Invalid auth subject type")

    async def __call__(
        self,
        auth_subject: AuthPrincipal[Customer | Member] = Depends(
            _CustomerPortalUnionWrite
        ),
    ) -> AuthPrincipal[Customer | Member]:
        return self._check_billing_permission(auth_subject)


class _UnionBillingRoleCheckRead(_UnionBillingRoleCheck):
    """Read-scope variant of billing role check."""

    async def __call__(
        self,
        auth_subject: AuthPrincipal[Customer | Member] = Depends(
            _CustomerPortalUnionRead
        ),
    ) -> AuthPrincipal[Customer | Member]:
        return self._check_billing_permission(auth_subject)


CustomerPortalUnionBillingRead = Annotated[
    AuthPrincipal[Customer | Member],
    Depends(_UnionBillingRoleCheckRead(allowed_roles=_union_billing_roles)),
]

CustomerPortalUnionBillingWrite = Annotated[
    AuthPrincipal[Customer | Member],
    Depends(_UnionBillingRoleCheck(allowed_roles=_union_billing_roles)),
]
