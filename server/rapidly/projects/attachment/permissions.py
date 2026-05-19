"""Auth dependencies for work-item attachment routes."""

from typing import Annotated

from fastapi import Depends

from rapidly.identity.auth.dependencies import Authenticator
from rapidly.identity.auth.models import AuthPrincipal, User, Workspace
from rapidly.identity.auth.scope import Scope

_AttachmentsRead = Authenticator(
    required_scopes={
        Scope.web_read,
        Scope.web_write,
        Scope.work_item_attachments_read,
        Scope.work_item_attachments_write,
    },
    allowed_subjects={User, Workspace},
)
WorkItemAttachmentsRead = Annotated[
    AuthPrincipal[User | Workspace], Depends(_AttachmentsRead)
]

_AttachmentsWrite = Authenticator(
    required_scopes={Scope.web_write, Scope.work_item_attachments_write},
    allowed_subjects={User, Workspace},
)
WorkItemAttachmentsWrite = Annotated[
    AuthPrincipal[User | Workspace], Depends(_AttachmentsWrite)
]
