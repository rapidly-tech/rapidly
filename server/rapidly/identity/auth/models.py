"""Defines the ``AuthPrincipal`` value object and subject-type predicates.

``AuthPrincipal`` bundles the authenticated *subject*, its allowed *scopes*,
and the originating *session*.  Companion type-guard helpers allow callers to
refine the generic subject without manual ``isinstance`` branching.
"""

from functools import cached_property
from typing import Generic, TypeGuard, TypeVar

from rapidly.enums import RateLimitGroup
from rapidly.models import (
    Customer,
    CustomerSession,
    Member,
    MemberSession,
    OAuth2Token,
    User,
    UserSession,
    Workspace,
    WorkspaceAccessToken,
)

from .scope import Scope

# ── Subject / session type unions ──────────────────────────────────────


class Anonymous:
    """Placeholder type for requests that carry no credentials."""

    __slots__ = ()


Subject = User | Workspace | Customer | Member | Anonymous
SubjectType = (
    type[User] | type[Workspace] | type[Customer] | type[Member] | type[Anonymous]
)
Session = (
    UserSession | WorkspaceAccessToken | OAuth2Token | CustomerSession | MemberSession
)

# ── Rate-limit label prefixes ─────────────────────────────────────────

_RL_PREFIX_MAP: dict[type, str] = {
    User: "user",
    Workspace: "workspace",
    Customer: "customer",
    Member: "member",
    Anonymous: "anonymous",
}

S = TypeVar("S", bound=Subject, covariant=True)


# ── Core principal wrapper ─────────────────────────────────────────────


class AuthPrincipal(Generic[S]):  # noqa: UP046 # Don't use the new syntax as it allows us to force covariant typing
    """Read-only auth envelope that accompanies each request through the stack."""

    __slots__ = ("__dict__", "scopes", "session", "subject")

    subject: S
    scopes: set[Scope]
    session: Session | None

    def __init__(self, subject: S, scopes: set[Scope], session: Session | None) -> None:
        self.subject = subject
        self.scopes = scopes
        self.session = session

    # ── Rate limiting ──────────────────────────────────────────────────

    @cached_property
    def rate_limit_key(self) -> tuple[str, RateLimitGroup]:
        return self.rate_limit_user, self.rate_limit_group

    @cached_property
    def rate_limit_user(self) -> str:
        if isinstance(self.session, OAuth2Token):
            return f"oauth2_client:{self.session.client_id}"

        prefix = _RL_PREFIX_MAP.get(type(self.subject), "unknown")
        subject_id = getattr(self.subject, "id", None)
        return f"{prefix}:{subject_id}" if subject_id else prefix

    @cached_property
    def rate_limit_group(self) -> RateLimitGroup:
        if isinstance(self.session, UserSession):
            return RateLimitGroup.web

        if isinstance(self.subject, Workspace):
            return self.subject.rate_limit_group

        if isinstance(self.session, OAuth2Token):
            return self.session.client.rate_limit_group

        return RateLimitGroup.default

    # ── Structured logging ─────────────────────────────────────────────

    @cached_property
    def log_context(self) -> dict[str, str]:
        baggage: dict[str, str] = {
            "subject_type": self.subject.__class__.__name__,
            "rate_limit_group": self.rate_limit_group.value,
            "rate_limit_user": self.rate_limit_user,
        }
        if isinstance(self.subject, User | Workspace | Customer | Member):
            baggage["subject_id"] = str(self.subject.id)

        if self.session:
            baggage["session_type"] = self.session.__class__.__name__
            if isinstance(self.session, UserSession) and self.session.is_impersonation:
                baggage["is_impersonation"] = "true"

        return baggage


# ── Type-guard functions ───────────────────────────────────────────────


def is_anonymous_principal[S: Subject](
    auth_subject: AuthPrincipal[S],
) -> TypeGuard[AuthPrincipal[Anonymous]]:
    """Check whether the principal represents a request with no credentials."""
    return isinstance(auth_subject.subject, Anonymous)


def is_user_principal[S: Subject](
    auth_subject: AuthPrincipal[S],
) -> TypeGuard[AuthPrincipal[User]]:
    """Confirm the principal is backed by a human user account."""
    return isinstance(auth_subject.subject, User)


def is_workspace_principal[S: Subject](
    auth_subject: AuthPrincipal[S],
) -> TypeGuard[AuthPrincipal[Workspace]]:
    """Confirm the principal is an workspace-level API token."""
    return isinstance(auth_subject.subject, Workspace)


def is_customer_principal[S: Subject](
    auth_subject: AuthPrincipal[S],
) -> TypeGuard[AuthPrincipal[Customer]]:
    """Confirm the principal belongs to a customer portal session."""
    return isinstance(auth_subject.subject, Customer)


def is_member_principal[S: Subject](
    auth_subject: AuthPrincipal[S],
) -> TypeGuard[AuthPrincipal[Member]]:
    """Confirm the principal belongs to a team member session."""
    return isinstance(auth_subject.subject, Member)


__all__ = [
    "Anonymous",
    "AuthPrincipal",
    "Customer",
    "Member",
    "Subject",
    "SubjectType",
    "User",
    "Workspace",
    "is_anonymous_principal",
    "is_customer_principal",
    "is_member_principal",
    "is_user_principal",
    "is_workspace_principal",
]
