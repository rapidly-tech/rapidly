"""Authentication dependencies for file sharing endpoints."""

from typing import Annotated

from fastapi import Depends

from rapidly.identity.auth.dependencies import Authenticator
from rapidly.identity.auth.models import AuthPrincipal, User, Workspace
from rapidly.identity.auth.scope import Scope

_FileSharingRead = Authenticator(
    required_scopes={Scope.web_read, Scope.web_write, Scope.file_sharing_read},
    allowed_subjects={User, Workspace},
)

FileSharingRead = Annotated[AuthPrincipal[User | Workspace], Depends(_FileSharingRead)]

_FileSharingWrite = Authenticator(
    required_scopes={Scope.web_write, Scope.file_sharing_write},
    allowed_subjects={User},
)

FileSharingWrite = Annotated[AuthPrincipal[User], Depends(_FileSharingWrite)]
