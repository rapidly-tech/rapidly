"""Auth dependencies for project-member invite routes."""

from typing import Annotated

from fastapi import Depends

from rapidly.identity.auth.dependencies import Authenticator
from rapidly.identity.auth.models import AuthPrincipal, User, Workspace
from rapidly.identity.auth.scope import Scope

_InvitesRead = Authenticator(
    required_scopes={
        Scope.web_read,
        Scope.web_write,
        Scope.project_member_invites_read,
        Scope.project_member_invites_write,
    },
    allowed_subjects={User, Workspace},
)
InvitesRead = Annotated[AuthPrincipal[User | Workspace], Depends(_InvitesRead)]

# Admin write — creating, revoking. Workspace tokens allowed since
# they're implicit admins of every project.
_InvitesAdmin = Authenticator(
    required_scopes={Scope.web_write, Scope.project_member_invites_write},
    allowed_subjects={User, Workspace},
)
InvitesAdmin = Annotated[AuthPrincipal[User | Workspace], Depends(_InvitesAdmin)]

# Self write — accepting, declining. User-only because only a User
# can take the action "as the invitee."
_InvitesSelf = Authenticator(
    required_scopes={Scope.web_write, Scope.project_member_invites_write},
    allowed_subjects={User},
)
InvitesSelf = Annotated[AuthPrincipal[User], Depends(_InvitesSelf)]
