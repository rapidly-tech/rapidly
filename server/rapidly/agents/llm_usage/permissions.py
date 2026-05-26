"""Auth dependencies for the LlmUsage read API.

Mirrors the IntegrationCredential pattern — read scope covers
both metadata reads and rollup queries; no write scope because
the API itself is read-only (writes happen inside the LLM
handler as part of run execution).
"""

from typing import Annotated

from fastapi import Depends

from rapidly.identity.auth.dependencies import Authenticator
from rapidly.identity.auth.models import AuthPrincipal, User, Workspace
from rapidly.identity.auth.scope import Scope

_LlmUsageRead = Authenticator(
    required_scopes={
        Scope.web_read,
        Scope.web_write,
        Scope.integration_credentials_read,
        Scope.integration_credentials_write,
    },
    allowed_subjects={User, Workspace},
)
LlmUsageRead = Annotated[AuthPrincipal[User | Workspace], Depends(_LlmUsageRead)]
