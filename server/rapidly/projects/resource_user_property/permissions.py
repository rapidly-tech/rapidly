"""Auth dependencies for cycle/module user-property routes.

User-only on both sides for the same reason as #714: workspace tokens
have no User to attribute, and these are per-user private prefs.
"""

from typing import Annotated

from fastapi import Depends

from rapidly.identity.auth.dependencies import Authenticator
from rapidly.identity.auth.models import AuthPrincipal, User
from rapidly.identity.auth.scope import Scope

# ── Cycles ───────────────────────────────────────────────────────────

_CyclePropsRead = Authenticator(
    required_scopes={
        Scope.web_read,
        Scope.web_write,
        Scope.project_cycle_user_properties_read,
        Scope.project_cycle_user_properties_write,
    },
    allowed_subjects={User},
)
CyclePropsRead = Annotated[AuthPrincipal[User], Depends(_CyclePropsRead)]

_CyclePropsWrite = Authenticator(
    required_scopes={Scope.web_write, Scope.project_cycle_user_properties_write},
    allowed_subjects={User},
)
CyclePropsWrite = Annotated[AuthPrincipal[User], Depends(_CyclePropsWrite)]


# ── Modules ──────────────────────────────────────────────────────────

_ModulePropsRead = Authenticator(
    required_scopes={
        Scope.web_read,
        Scope.web_write,
        Scope.project_module_user_properties_read,
        Scope.project_module_user_properties_write,
    },
    allowed_subjects={User},
)
ModulePropsRead = Annotated[AuthPrincipal[User], Depends(_ModulePropsRead)]

_ModulePropsWrite = Authenticator(
    required_scopes={Scope.web_write, Scope.project_module_user_properties_write},
    allowed_subjects={User},
)
ModulePropsWrite = Annotated[AuthPrincipal[User], Depends(_ModulePropsWrite)]
