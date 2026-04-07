"""Consent grant persistence.

Tracks which scopes a subject (user or workspace) has granted to each
OAuth2 client, enabling silent re-authorization when the requested scope
is a subset of what was previously approved.
"""

import uuid

from sqlalchemy import Select, select

from rapidly.core.db.postgres import Session as SyncSession
from rapidly.models import OAuth2Grant

from ..sub_type import SubType


def _apply_sub_filter(
    stmt: Select[tuple[OAuth2Grant]],
    sub_type: SubType,
    sub_id: uuid.UUID,
) -> Select[tuple[OAuth2Grant]]:
    """Narrow a query to the correct subject column based on ``sub_type``."""
    if sub_type == SubType.user:
        return stmt.where(OAuth2Grant.user_id == sub_id)
    elif sub_type == SubType.workspace:
        return stmt.where(OAuth2Grant.workspace_id == sub_id)
    raise NotImplementedError(f"Unsupported sub_type: {sub_type}")


class OAuth2GrantService:
    """Manage per-client consent records."""

    def create_or_update_grant(
        self,
        session: SyncSession,
        *,
        sub_type: SubType,
        sub_id: uuid.UUID,
        client_id: str,
        scope: str,
    ) -> OAuth2Grant:
        """Upsert the consent record: create if new, update scope if existing."""
        existing = self._find_grant(
            session, sub_type=sub_type, sub_id=sub_id, client_id=client_id
        )
        if existing is not None:
            existing.scope = scope
            session.add(existing)
            session.flush()
            return existing

        grant = OAuth2Grant(client_id=client_id, scope=scope)
        if sub_type == SubType.user:
            grant.user_id = sub_id
        elif sub_type == SubType.workspace:
            grant.workspace_id = sub_id
        else:
            raise NotImplementedError(f"Unsupported sub_type: {sub_type}")
        session.add(grant)
        session.flush()
        return grant

    def has_granted_scope(
        self,
        session: SyncSession,
        *,
        sub_type: SubType,
        sub_id: uuid.UUID,
        client_id: str,
        scope: str,
    ) -> bool:
        """Return True if every scope in ``scope`` is covered by a prior grant."""
        grant = self._find_grant(
            session, sub_type=sub_type, sub_id=sub_id, client_id=client_id
        )
        if grant is None:
            return False
        requested = set(scope.strip().split())
        return requested.issubset(grant.scopes)

    def _find_grant(
        self,
        session: SyncSession,
        *,
        sub_type: SubType,
        sub_id: uuid.UUID,
        client_id: str,
    ) -> OAuth2Grant | None:
        """Look up the consent record for a given subject + client pair."""
        stmt = select(OAuth2Grant).where(OAuth2Grant.client_id == client_id)
        stmt = _apply_sub_filter(stmt, sub_type, sub_id)
        return session.execute(stmt).unique().scalar_one_or_none()


oauth2_grant = OAuth2GrantService()
