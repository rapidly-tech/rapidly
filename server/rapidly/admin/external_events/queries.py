"""Admin external-event query repository.

Centralises direct DB access for the admin external-events module, following
the convention that API handlers never execute raw ``select()`` /
``session.execute()`` calls themselves.
"""

from __future__ import annotations

import uuid

from sqlalchemy import Select, or_

from rapidly.core.queries import Repository
from rapidly.core.queries.utils import escape_like
from rapidly.models import ExternalEvent


class AdminExternalEventRepository(Repository[ExternalEvent]):
    """Admin-specific queries for the external-event list view."""

    model = ExternalEvent

    def get_list_statement(
        self,
        *,
        query: str | None = None,
        handled: bool | None = None,
    ) -> Select[tuple[ExternalEvent]]:
        """Return a filterable statement for listing external events.

        Optionally filters by:
        - UUID exact match on event ID
        - Partial text match on ``external_id`` or ``task_name``
        - ``is_handled`` boolean status
        """
        stmt = self.get_base_statement()

        if query:
            try:
                stmt = stmt.where(ExternalEvent.id == uuid.UUID(query))
            except ValueError:
                escaped = escape_like(query)
                stmt = stmt.where(
                    or_(
                        ExternalEvent.external_id.ilike(f"%{escaped}%"),
                        ExternalEvent.task_name.ilike(f"%{escaped}%"),
                    )
                )

        if handled is not None:
            stmt = stmt.where(ExternalEvent.is_handled == handled)

        return stmt
