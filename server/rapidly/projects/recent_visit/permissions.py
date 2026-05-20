"""Auth dependencies for recent-visit routes.

User-only on both sides. Workspace tokens have no User to attribute
per-user history to, and recents are private — no admin escape hatch.
"""

from typing import Annotated

from fastapi import Depends

from rapidly.identity.auth.dependencies import Authenticator
from rapidly.identity.auth.models import AuthPrincipal, User
from rapidly.identity.auth.scope import Scope

_RecentVisitsRead = Authenticator(
    required_scopes={
        Scope.web_read,
        Scope.web_write,
        Scope.recent_visits_read,
        Scope.recent_visits_write,
    },
    allowed_subjects={User},
)
RecentVisitsRead = Annotated[AuthPrincipal[User], Depends(_RecentVisitsRead)]

_RecentVisitsWrite = Authenticator(
    required_scopes={Scope.web_write, Scope.recent_visits_write},
    allowed_subjects={User},
)
RecentVisitsWrite = Annotated[AuthPrincipal[User], Depends(_RecentVisitsWrite)]
