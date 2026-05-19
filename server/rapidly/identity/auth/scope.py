"""OAuth2 scope definitions and display-name registry.

Scopes follow a ``resource:action`` naming convention.  The ``web_read``
and ``web_write`` scopes are reserved for first-party browser sessions
and never exposed to third-party OAuth2 clients.
"""

from enum import StrEnum

from pydantic import GetJsonSchemaHandler
from pydantic.json_schema import JsonSchemaValue
from pydantic_core import core_schema as cs


class Scope(StrEnum):
    """All OAuth2 scopes recognised by the platform."""

    # OIDC standard
    openid = "openid"
    profile = "profile"
    email = "email"

    # User
    user_write = "user:write"

    # First-party web sessions (reserved — never granted to third parties)
    web_read = "web:read"
    web_write = "web:write"

    # Workspaces
    workspaces_read = "workspaces:read"
    workspaces_write = "workspaces:write"

    # Custom fields
    custom_fields_read = "custom_fields:read"
    custom_fields_write = "custom_fields:write"

    # Shares (file sharing products)
    shares_read = "shares:read"
    shares_write = "shares:write"

    # Events
    events_read = "events:read"
    events_write = "events:write"

    # Files
    files_read = "files:read"
    files_write = "files:write"

    # Customers
    customers_read = "customers:read"
    customers_write = "customers:write"

    # Members
    members_read = "members:read"
    members_write = "members:write"

    # Sessions
    customer_sessions_write = "customer_sessions:write"
    member_sessions_write = "member_sessions:write"

    # Payments & metrics
    payments_read = "payments:read"
    metrics_read = "metrics:read"

    # Webhooks
    webhooks_read = "webhooks:read"
    webhooks_write = "webhooks:write"

    # Customer portal
    customer_portal_read = "customer_portal:read"
    customer_portal_write = "customer_portal:write"

    # Notifications
    notifications_read = "notifications:read"
    notifications_write = "notifications:write"
    notification_recipients_read = "notification_recipients:read"
    notification_recipients_write = "notification_recipients:write"

    # Workspace access tokens
    workspace_access_tokens_read = "workspace_access_tokens:read"
    workspace_access_tokens_write = "workspace_access_tokens:write"

    # File sharing
    file_sharing_read = "file_sharing:read"
    file_sharing_write = "file_sharing:write"

    # Projects (project management product)
    projects_read = "projects:read"
    projects_write = "projects:write"
    project_members_read = "project_members:read"
    project_members_write = "project_members:write"
    project_states_read = "project_states:read"
    project_states_write = "project_states:write"
    project_labels_read = "project_labels:read"
    project_labels_write = "project_labels:write"
    project_estimates_read = "project_estimates:read"
    project_estimates_write = "project_estimates:write"
    work_items_read = "work_items:read"
    work_items_write = "work_items:write"
    work_item_comments_read = "work_item_comments:read"
    work_item_comments_write = "work_item_comments:write"
    work_item_relations_read = "work_item_relations:read"
    work_item_relations_write = "work_item_relations:write"
    project_cycles_read = "project_cycles:read"
    project_cycles_write = "project_cycles:write"
    project_modules_read = "project_modules:read"
    project_modules_write = "project_modules:write"
    work_item_activities_read = "work_item_activities:read"
    project_pages_read = "project_pages:read"
    project_pages_write = "project_pages:write"
    user_favorites_read = "user_favorites:read"
    user_favorites_write = "user_favorites:write"

    @classmethod
    def __get_pydantic_json_schema__(
        cls, core_schema: cs.CoreSchema, handler: GetJsonSchemaHandler
    ) -> JsonSchemaValue:
        json_schema = handler(core_schema)
        json_schema = handler.resolve_ref_schema(json_schema)
        json_schema["enumNames"] = SCOPES_SUPPORTED_DISPLAY_NAMES
        return json_schema


# ── Scope sets ─────────────────────────────────────────────────────────

RESERVED_SCOPES: frozenset[Scope] = frozenset({Scope.web_read, Scope.web_write})
SCOPES_SUPPORTED: list[str] = [s.value for s in Scope if s not in RESERVED_SCOPES]
SCOPES_SUPPORTED_DISPLAY_NAMES: dict[Scope, str] = {
    Scope.openid: "OpenID",
    Scope.profile: "Read your profile information",
    Scope.email: "Read your email address",
    Scope.web_read: "Web Read Access",
    Scope.web_write: "Web Write Access",
    Scope.user_write: "Delete your user account",
    Scope.workspaces_read: "Read your workspaces",
    Scope.workspaces_write: "Create or modify workspaces",
    Scope.custom_fields_read: "Read custom fields",
    Scope.custom_fields_write: "Create or modify custom fields",
    Scope.shares_read: "Read shares",
    Scope.shares_write: "Create or modify shares",
    Scope.events_read: "Read events",
    Scope.events_write: "Create events",
    Scope.files_read: "Read file uploads",
    Scope.files_write: "Create or modify file uploads",
    Scope.customers_read: "Read customers",
    Scope.customers_write: "Create or modify customers",
    Scope.members_read: "Read members",
    Scope.members_write: "Create or modify members",
    Scope.customer_sessions_write: "Create or modify customer sessions",
    Scope.member_sessions_write: "Create or modify member sessions",
    Scope.payments_read: "Read payments",
    Scope.metrics_read: "Read metrics",
    Scope.webhooks_read: "Read webhooks",
    Scope.webhooks_write: "Create or modify webhooks",
    Scope.customer_portal_read: "Read your files and access",
    Scope.customer_portal_write: "Manage your files and access",
    Scope.notifications_read: "Read notifications",
    Scope.notifications_write: "Mark notifications as read",
    Scope.notification_recipients_read: "Read notification recipients",
    Scope.notification_recipients_write: "Create or modify notification recipients",
    Scope.workspace_access_tokens_read: "Read workspace access tokens",
    Scope.workspace_access_tokens_write: "Create or modify workspace access tokens",
    Scope.file_sharing_read: "Read file sharing sessions",
    Scope.file_sharing_write: "Create or modify file sharing sessions",
    Scope.projects_read: "Read projects",
    Scope.projects_write: "Create or modify projects",
    Scope.project_members_read: "Read project members",
    Scope.project_members_write: "Create or modify project members",
    Scope.project_states_read: "Read project workflow states",
    Scope.project_states_write: "Create or modify project workflow states",
    Scope.project_labels_read: "Read project labels",
    Scope.project_labels_write: "Create or modify project labels",
    Scope.project_estimates_read: "Read project estimation scales",
    Scope.project_estimates_write: "Create or modify project estimation scales",
    Scope.work_items_read: "Read work items",
    Scope.work_items_write: "Create or modify work items",
    Scope.work_item_comments_read: "Read work item comments",
    Scope.work_item_comments_write: "Create or modify work item comments",
    Scope.work_item_relations_read: "Read work item relations",
    Scope.work_item_relations_write: "Create or modify work item relations",
    Scope.project_cycles_read: "Read project cycles",
    Scope.project_cycles_write: "Create or modify project cycles",
    Scope.project_modules_read: "Read project modules",
    Scope.project_modules_write: "Create or modify project modules",
    Scope.work_item_activities_read: "Read work-item activity history",
    Scope.project_pages_read: "Read project pages",
    Scope.project_pages_write: "Create or modify project pages",
    Scope.user_favorites_read: "Read your favourites",
    Scope.user_favorites_write: "Create or modify your favourites",
}


# ── Parsing helpers ────────────────────────────────────────────────────


def scope_to_set(scope: str) -> set[Scope]:
    """Parse a space-separated scope string into a set of ``Scope`` values."""
    return {Scope(x) for x in scope.strip().split()}


def scope_to_list(scope: str) -> list[Scope]:
    """Parse a space-separated scope string into a list of ``Scope`` values."""
    return list(scope_to_set(scope))
