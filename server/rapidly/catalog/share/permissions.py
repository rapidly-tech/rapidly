"""Authentication dependencies for share endpoints.

Defines read and write access gates for share management, allowing
both human users and workspace-scoped API tokens.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends

from rapidly.identity.auth.dependencies import Authenticator
from rapidly.identity.auth.models import AuthPrincipal, User, Workspace
from rapidly.identity.auth.scope import Scope

# ── Read access ──────────────────────────────────────────────────────

_creator_shares_read = Authenticator(
    required_scopes={
        Scope.web_read,
        Scope.web_write,
        Scope.shares_read,
        Scope.shares_write,
    },
    allowed_subjects={User, Workspace},
)

CreatorSharesRead = Annotated[
    AuthPrincipal[User | Workspace], Depends(_creator_shares_read)
]

# ── Write access ─────────────────────────────────────────────────────

_creator_shares_write = Authenticator(
    required_scopes={
        Scope.web_write,
        Scope.shares_write,
    },
    allowed_subjects={User, Workspace},
)

CreatorSharesWrite = Annotated[
    AuthPrincipal[User | Workspace], Depends(_creator_shares_write)
]
