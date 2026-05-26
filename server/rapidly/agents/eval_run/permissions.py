"""Auth dependencies for eval_run routes.

Read scope follows the datasets pattern — operators who can read
datasets can read evals against them. Write scope requires
``datasets:write`` because triggering an eval consumes LLM
budget against the workspace's credentials.
"""

from typing import Annotated

from fastapi import Depends

from rapidly.identity.auth.dependencies import Authenticator
from rapidly.identity.auth.models import AuthPrincipal, User, Workspace
from rapidly.identity.auth.scope import Scope

_EvalRunsRead = Authenticator(
    required_scopes={
        Scope.web_read,
        Scope.web_write,
        Scope.datasets_read,
        Scope.datasets_write,
    },
    allowed_subjects={User, Workspace},
)
EvalRunsRead = Annotated[AuthPrincipal[User | Workspace], Depends(_EvalRunsRead)]

_EvalRunsWrite = Authenticator(
    required_scopes={Scope.web_write, Scope.datasets_write},
    allowed_subjects={User, Workspace},
)
EvalRunsWrite = Annotated[AuthPrincipal[User | Workspace], Depends(_EvalRunsWrite)]
