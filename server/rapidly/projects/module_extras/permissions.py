"""Auth dependencies for module-member + module-link routes."""

from typing import Annotated

from fastapi import Depends

from rapidly.identity.auth.dependencies import Authenticator
from rapidly.identity.auth.models import AuthPrincipal, User, Workspace
from rapidly.identity.auth.scope import Scope

# ── Members ──────────────────────────────────────────────────────────

_MembersRead = Authenticator(
    required_scopes={
        Scope.web_read,
        Scope.web_write,
        Scope.project_module_members_read,
        Scope.project_module_members_write,
    },
    allowed_subjects={User, Workspace},
)
ModuleMembersRead = Annotated[AuthPrincipal[User | Workspace], Depends(_MembersRead)]

_MembersWrite = Authenticator(
    required_scopes={Scope.web_write, Scope.project_module_members_write},
    allowed_subjects={User, Workspace},
)
ModuleMembersWrite = Annotated[AuthPrincipal[User | Workspace], Depends(_MembersWrite)]


# ── Links ────────────────────────────────────────────────────────────

_LinksRead = Authenticator(
    required_scopes={
        Scope.web_read,
        Scope.web_write,
        Scope.project_module_links_read,
        Scope.project_module_links_write,
    },
    allowed_subjects={User, Workspace},
)
ModuleLinksRead = Annotated[AuthPrincipal[User | Workspace], Depends(_LinksRead)]

_LinksWrite = Authenticator(
    required_scopes={Scope.web_write, Scope.project_module_links_write},
    allowed_subjects={User, Workspace},
)
ModuleLinksWrite = Annotated[AuthPrincipal[User | Workspace], Depends(_LinksWrite)]
