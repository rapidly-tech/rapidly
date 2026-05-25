"""Auth dependencies for workflow routes.

Read scope covers all workflow surfaces; write covers create/update/
delete. ``runs_trigger`` is a separate scope (defined in scope.py)
that an API-key issuer can grant in isolation — operators may want
to let an external integration start runs without granting full
edit rights to the workflow.
"""

from typing import Annotated

from fastapi import Depends

from rapidly.identity.auth.dependencies import Authenticator
from rapidly.identity.auth.models import AuthPrincipal, User, Workspace
from rapidly.identity.auth.scope import Scope

_WorkflowsRead = Authenticator(
    required_scopes={
        Scope.web_read,
        Scope.web_write,
        Scope.workflows_read,
        Scope.workflows_write,
    },
    allowed_subjects={User, Workspace},
)
WorkflowsRead = Annotated[AuthPrincipal[User | Workspace], Depends(_WorkflowsRead)]

_WorkflowsWrite = Authenticator(
    required_scopes={Scope.web_write, Scope.workflows_write},
    allowed_subjects={User, Workspace},
)
WorkflowsWrite = Annotated[AuthPrincipal[User | Workspace], Depends(_WorkflowsWrite)]
