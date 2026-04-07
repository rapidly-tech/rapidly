"""Admin share query repository.

Centralises direct DB access for the admin shares module, following the
convention that API handlers never execute raw ``select()`` /
``session.execute()`` calls themselves.
"""

from __future__ import annotations

import uuid

from sqlalchemy import Select, or_
from sqlalchemy.orm import contains_eager

from rapidly.core.queries import Repository
from rapidly.core.queries.utils import escape_like
from rapidly.models import Share, Workspace


class AdminShareRepository(Repository[Share]):
    """Admin-specific queries for the share list view."""

    model = Share

    def get_list_statement(
        self,
        *,
        query: str | None = None,
    ) -> Select[tuple[Share]]:
        """Return a statement for listing shares with workspace eagerly loaded.

        Optionally filters by UUID match (share or workspace) or partial
        text match on share name / workspace slug / workspace name.
        """
        stmt = (
            self.get_base_statement()
            .join(Workspace, Share.workspace_id == Workspace.id)
            .options(contains_eager(Share.workspace))
        )

        if query:
            try:
                q_uuid = uuid.UUID(query)
                stmt = stmt.where(or_(Share.id == q_uuid, Share.workspace_id == q_uuid))
            except ValueError:
                escaped = escape_like(query)
                stmt = stmt.where(
                    or_(
                        Share.name.ilike(f"%{escaped}%"),
                        Workspace.slug.ilike(f"%{escaped}%"),
                        Workspace.name.ilike(f"%{escaped}%"),
                    )
                )

        return stmt
