"""Auth dependencies for project deploy-board routes."""

from typing import Annotated

from fastapi import Depends

from rapidly.identity.auth.dependencies import Authenticator
from rapidly.identity.auth.models import AuthPrincipal, User, Workspace
from rapidly.identity.auth.scope import Scope

_DeployBoardsRead = Authenticator(
    required_scopes={
        Scope.web_read,
        Scope.web_write,
        Scope.project_deploy_boards_read,
        Scope.project_deploy_boards_write,
    },
    allowed_subjects={User, Workspace},
)
DeployBoardsRead = Annotated[
    AuthPrincipal[User | Workspace], Depends(_DeployBoardsRead)
]

_DeployBoardsWrite = Authenticator(
    required_scopes={Scope.web_write, Scope.project_deploy_boards_write},
    allowed_subjects={User, Workspace},
)
DeployBoardsWrite = Annotated[
    AuthPrincipal[User | Workspace], Depends(_DeployBoardsWrite)
]
