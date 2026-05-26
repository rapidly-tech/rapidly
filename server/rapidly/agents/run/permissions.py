"""Auth dependencies for run routes.

Read covers list/get; trigger is a separate scope from
workflows_write so an API key can start runs without granting full
workflow-edit rights. Cancel uses the same scope as trigger — an
operator who can start a run can also stop it.
"""

from typing import Annotated

from fastapi import Depends

from rapidly.identity.auth.dependencies import Authenticator
from rapidly.identity.auth.models import AuthPrincipal, User, Workspace
from rapidly.identity.auth.scope import Scope

_RunsRead = Authenticator(
    required_scopes={
        Scope.web_read,
        Scope.web_write,
        Scope.workflows_read,
        Scope.workflows_write,
    },
    allowed_subjects={User, Workspace},
)
RunsRead = Annotated[AuthPrincipal[User | Workspace], Depends(_RunsRead)]

_RunsTrigger = Authenticator(
    required_scopes={Scope.web_write, Scope.runs_trigger},
    allowed_subjects={User, Workspace},
)
RunsTrigger = Annotated[AuthPrincipal[User | Workspace], Depends(_RunsTrigger)]
