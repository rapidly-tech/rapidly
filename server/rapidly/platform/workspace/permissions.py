"""Workspace auth dependencies: scope-checked authenticators.

Pre-built ``Depends`` aliases that enforce user or workspace
authentication with the appropriate ``workspaces:read`` or
``workspaces:write`` scope.
"""

from typing import Annotated

from fastapi import Depends

from rapidly.identity.auth.dependencies import Authenticator
from rapidly.identity.auth.models import Anonymous, AuthPrincipal, User, Workspace
from rapidly.identity.auth.scope import Scope

WorkspacesRead = Annotated[
    AuthPrincipal[User | Workspace],
    Depends(
        Authenticator(
            required_scopes={
                Scope.web_read,
                Scope.web_write,
                Scope.workspaces_read,
                Scope.workspaces_write,
            },
            allowed_subjects={User, Workspace},
        )
    ),
]

WorkspacesWrite = Annotated[
    AuthPrincipal[User | Workspace],
    Depends(
        Authenticator(
            required_scopes={
                Scope.web_write,
                Scope.workspaces_write,
            },
            allowed_subjects={User, Workspace},
        )
    ),
]

WorkspacesCreate = Annotated[
    AuthPrincipal[User],
    Depends(
        Authenticator(
            required_scopes={
                Scope.web_write,
                Scope.workspaces_write,
            },
            allowed_subjects={User},
        )
    ),
]

WorkspacesWriteUser = Annotated[
    AuthPrincipal[User],
    Depends(
        Authenticator(
            required_scopes={
                Scope.web_write,
                Scope.workspaces_write,
            },
            allowed_subjects={User},
        )
    ),
]

WorkspacesReadOrAnonymous = Annotated[
    AuthPrincipal[User | Workspace | Anonymous],
    Depends(
        Authenticator(
            required_scopes=set(),  # No required scopes for this authenticator
            allowed_subjects={User, Workspace, Anonymous},
        )
    ),
]
