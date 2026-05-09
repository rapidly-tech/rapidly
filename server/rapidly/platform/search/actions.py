"""Cross-entity full-text search service.

Performs a unified search across products, customers, and workspaces
using PostgreSQL's ``ts_vector`` GIN indexes with rank-based ordering.
"""

import uuid

from rapidly.core.db.postgres import AsyncReadSession
from rapidly.identity.auth.models import AuthPrincipal, User
from rapidly.identity.auth.scope import Scope

from .queries import SearchRepository
from .types import (
    SearchResult,
    SearchResultTypeAdapter,
)

# ── Helpers ──


def _try_parse_uuid(query: str) -> uuid.UUID | None:
    try:
        return uuid.UUID(query.strip())
    except (ValueError, AttributeError):
        return None


def _has_shares_scope(auth_subject: AuthPrincipal[User]) -> bool:
    return bool(
        auth_subject.scopes
        & {
            Scope.web_read,
            Scope.web_write,
            Scope.shares_read,
            Scope.shares_write,
        }
    )


def _has_customers_scope(auth_subject: AuthPrincipal[User]) -> bool:
    return bool(
        auth_subject.scopes
        & {
            Scope.web_read,
            Scope.web_write,
            Scope.customers_read,
            Scope.customers_write,
        }
    )


# ── Query execution ──


async def search(
    session: AsyncReadSession,
    auth_subject: AuthPrincipal[User],
    *,
    workspace_id: uuid.UUID,
    query: str,
    limit: int = 20,
) -> list[SearchResult]:
    query_uuid = _try_parse_uuid(query)

    repo = SearchRepository.from_session(session)
    rows = await repo.search(
        workspace_id=workspace_id,
        user_id=auth_subject.subject.id,
        query=query,
        query_uuid=query_uuid,
        has_shares_scope=_has_shares_scope(auth_subject),
        has_customers_scope=_has_customers_scope(auth_subject),
        limit=limit,
    )
    return [SearchResultTypeAdapter.validate_python(row) for row in rows]
