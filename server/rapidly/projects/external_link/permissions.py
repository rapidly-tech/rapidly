"""Auth dependencies for work-item external link routes."""

from typing import Annotated

from fastapi import Depends

from rapidly.identity.auth.dependencies import Authenticator
from rapidly.identity.auth.models import AuthPrincipal, User, Workspace
from rapidly.identity.auth.scope import Scope

_LinksRead = Authenticator(
    required_scopes={
        Scope.web_read,
        Scope.web_write,
        Scope.work_item_links_read,
        Scope.work_item_links_write,
    },
    allowed_subjects={User, Workspace},
)
WorkItemLinksRead = Annotated[AuthPrincipal[User | Workspace], Depends(_LinksRead)]

_LinksWrite = Authenticator(
    required_scopes={Scope.web_write, Scope.work_item_links_write},
    allowed_subjects={User, Workspace},
)
WorkItemLinksWrite = Annotated[AuthPrincipal[User | Workspace], Depends(_LinksWrite)]
