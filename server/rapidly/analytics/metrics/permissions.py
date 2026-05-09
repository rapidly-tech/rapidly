"""Access control dependencies for metrics routes."""

from typing import Annotated

from fastapi import Depends

from rapidly.identity.auth.dependencies import Authenticator
from rapidly.identity.auth.models import AuthPrincipal, User, Workspace
from rapidly.identity.auth.scope import Scope

_MetricsRead = Authenticator(
    required_scopes={Scope.web_read, Scope.web_write, Scope.metrics_read},
    allowed_subjects={User, Workspace},
)
MetricsRead = Annotated[AuthPrincipal[User | Workspace], Depends(_MetricsRead)]
