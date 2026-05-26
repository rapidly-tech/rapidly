"""Auth dependencies for dataset routes.

Two scopes — read covers list/get on both datasets + cases; write
covers create/update/delete on both. Cases don't get a separate
scope because operators editing a dataset's cases need the same
trust level as editing the dataset itself.
"""

from typing import Annotated

from fastapi import Depends

from rapidly.identity.auth.dependencies import Authenticator
from rapidly.identity.auth.models import AuthPrincipal, User, Workspace
from rapidly.identity.auth.scope import Scope

_DatasetsRead = Authenticator(
    required_scopes={
        Scope.web_read,
        Scope.web_write,
        Scope.datasets_read,
        Scope.datasets_write,
    },
    allowed_subjects={User, Workspace},
)
DatasetsRead = Annotated[AuthPrincipal[User | Workspace], Depends(_DatasetsRead)]

_DatasetsWrite = Authenticator(
    required_scopes={Scope.web_write, Scope.datasets_write},
    allowed_subjects={User, Workspace},
)
DatasetsWrite = Annotated[AuthPrincipal[User | Workspace], Depends(_DatasetsWrite)]
