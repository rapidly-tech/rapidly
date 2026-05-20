"""Auth dependencies for intake-work-item routes."""

from typing import Annotated

from fastapi import Depends

from rapidly.identity.auth.dependencies import Authenticator
from rapidly.identity.auth.models import AuthPrincipal, User, Workspace
from rapidly.identity.auth.scope import Scope

_IntakeRead = Authenticator(
    required_scopes={
        Scope.web_read,
        Scope.web_write,
        Scope.intake_work_items_read,
        Scope.intake_work_items_write,
    },
    allowed_subjects={User, Workspace},
)
IntakeRead = Annotated[AuthPrincipal[User | Workspace], Depends(_IntakeRead)]

_IntakeWrite = Authenticator(
    required_scopes={Scope.web_write, Scope.intake_work_items_write},
    allowed_subjects={User, Workspace},
)
IntakeWrite = Annotated[AuthPrincipal[User | Workspace], Depends(_IntakeWrite)]
