"""Auth dependencies for workflow_version routes.

Read is anyone with workflow read access. Write (publishing a new
version) requires the same scope as editing a workflow — versions
are an editorial action, not a runtime trigger."""

from typing import Annotated

from fastapi import Depends

from rapidly.identity.auth.dependencies import Authenticator
from rapidly.identity.auth.models import AuthPrincipal, User, Workspace
from rapidly.identity.auth.scope import Scope

_VersionsRead = Authenticator(
    required_scopes={
        Scope.web_read,
        Scope.web_write,
        Scope.workflows_read,
        Scope.workflows_write,
    },
    allowed_subjects={User, Workspace},
)
WorkflowVersionsRead = Annotated[
    AuthPrincipal[User | Workspace], Depends(_VersionsRead)
]

_VersionsWrite = Authenticator(
    required_scopes={Scope.web_write, Scope.workflows_write},
    # Publishing a version is workflow-author territory, not
    # runtime-trigger. Only User principals can do it for now —
    # workspace API tokens stay scoped to runs_trigger.
    allowed_subjects={User},
)
WorkflowVersionsWrite = Annotated[AuthPrincipal[User], Depends(_VersionsWrite)]
