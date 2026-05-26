"""Auth dependencies for IntegrationCredential routes.

Read scope covers list + get of credential **metadata** (not the
secret itself — the API never returns plaintext). Write scope
covers create + delete + default-toggle.

No ``runs_trigger`` overlap intentionally: triggering a workflow
run resolves credentials at the actor layer, not the API layer,
so a run-trigger token doesn't need credential read scope.
"""

from typing import Annotated

from fastapi import Depends

from rapidly.identity.auth.dependencies import Authenticator
from rapidly.identity.auth.models import AuthPrincipal, User, Workspace
from rapidly.identity.auth.scope import Scope

_IntegrationCredentialsRead = Authenticator(
    required_scopes={
        Scope.web_read,
        Scope.web_write,
        Scope.integration_credentials_read,
        Scope.integration_credentials_write,
    },
    allowed_subjects={User, Workspace},
)
IntegrationCredentialsRead = Annotated[
    AuthPrincipal[User | Workspace], Depends(_IntegrationCredentialsRead)
]

_IntegrationCredentialsWrite = Authenticator(
    required_scopes={Scope.web_write, Scope.integration_credentials_write},
    allowed_subjects={User, Workspace},
)
IntegrationCredentialsWrite = Annotated[
    AuthPrincipal[User | Workspace], Depends(_IntegrationCredentialsWrite)
]
