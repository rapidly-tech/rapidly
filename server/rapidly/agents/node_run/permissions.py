"""Auth dependencies for node_run routes.

Read-only surface — the engine is the only writer, and writes
happen via direct repository calls in M4.2, not through any HTTP
endpoint. So we expose just a read scope here.
"""

from typing import Annotated

from fastapi import Depends

from rapidly.identity.auth.dependencies import Authenticator
from rapidly.identity.auth.models import AuthPrincipal, User, Workspace
from rapidly.identity.auth.scope import Scope

_NodeRunsRead = Authenticator(
    required_scopes={
        Scope.web_read,
        Scope.web_write,
        Scope.workflows_read,
        Scope.workflows_write,
    },
    allowed_subjects={User, Workspace},
)
NodeRunsRead = Annotated[AuthPrincipal[User | Workspace], Depends(_NodeRunsRead)]
