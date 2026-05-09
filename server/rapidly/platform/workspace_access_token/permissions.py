"""Authentication dependencies for workspace access token endpoints."""

from typing import Annotated

from fastapi import Depends

from rapidly.identity.auth.dependencies import Authenticator
from rapidly.identity.auth.models import AuthPrincipal, User, Workspace
from rapidly.identity.auth.scope import Scope

_WorkspaceAccessTokensRead = Authenticator(
    required_scopes={
        Scope.web_read,
        Scope.web_write,
        Scope.workspace_access_tokens_read,
        Scope.workspace_access_tokens_write,
    },
    allowed_subjects={User, Workspace},
)
WorkspaceAccessTokensRead = Annotated[
    AuthPrincipal[User | Workspace], Depends(_WorkspaceAccessTokensRead)
]

_WorkspaceAccessTokensWrite = Authenticator(
    required_scopes={
        Scope.web_write,
        Scope.workspace_access_tokens_write,
    },
    allowed_subjects={User, Workspace},
)
WorkspaceAccessTokensWrite = Annotated[
    AuthPrincipal[User | Workspace], Depends(_WorkspaceAccessTokensWrite)
]
