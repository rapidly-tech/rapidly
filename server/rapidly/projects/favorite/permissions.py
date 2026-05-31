"""Auth dependencies for user favorite routes.

Favorites are user-bound: a workspace token has no notion of which user
created it, so it cannot meaningfully own a favorite.  Both read and
write routes therefore reject workspace tokens at the dependency layer.
"""

from typing import Annotated

from fastapi import Depends

from rapidly.identity.auth.dependencies import Authenticator
from rapidly.identity.auth.models import AuthPrincipal, User
from rapidly.identity.auth.scope import Scope

_FavoritesRead = Authenticator(
    required_scopes={
        Scope.web_read,
        Scope.web_write,
        Scope.user_favorites_read,
        Scope.user_favorites_write,
    },
    allowed_subjects={User},
)
UserFavoritesRead = Annotated[AuthPrincipal[User], Depends(_FavoritesRead)]

_FavoritesWrite = Authenticator(
    required_scopes={Scope.web_write, Scope.user_favorites_write},
    allowed_subjects={User},
)
UserFavoritesWrite = Annotated[AuthPrincipal[User], Depends(_FavoritesWrite)]
