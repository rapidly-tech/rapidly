"""Auth dependencies for project-user-property routes.

Both read and write are user-only — these are per-user records and
workspace-scoped tokens don't have a User identity to attribute.
"""

from typing import Annotated

from fastapi import Depends

from rapidly.identity.auth.dependencies import Authenticator
from rapidly.identity.auth.models import AuthPrincipal, User
from rapidly.identity.auth.scope import Scope

_PropertiesRead = Authenticator(
    required_scopes={
        Scope.web_read,
        Scope.web_write,
        Scope.project_user_properties_read,
        Scope.project_user_properties_write,
    },
    allowed_subjects={User},
)
UserPropertiesRead = Annotated[AuthPrincipal[User], Depends(_PropertiesRead)]

_PropertiesWrite = Authenticator(
    required_scopes={Scope.web_write, Scope.project_user_properties_write},
    allowed_subjects={User},
)
UserPropertiesWrite = Annotated[AuthPrincipal[User], Depends(_PropertiesWrite)]
