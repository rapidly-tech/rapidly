"""Admin webhook query repository.

Centralises direct DB access for the admin webhooks module, following the
convention that API handlers never execute raw ``select()`` /
``session.execute()`` calls themselves.
"""

from __future__ import annotations

import uuid

from sqlalchemy import Select, or_
from sqlalchemy.orm import contains_eager

from rapidly.core.queries import Repository
from rapidly.core.queries.utils import escape_like
from rapidly.models import WebhookEndpoint, Workspace


class AdminWebhookRepository(Repository[WebhookEndpoint]):
    """Admin-specific queries for the webhook list view."""

    model = WebhookEndpoint

    def get_list_statement(
        self,
        *,
        query: str | None = None,
    ) -> Select[tuple[WebhookEndpoint]]:
        """Return a statement for listing webhooks with workspace eagerly loaded.

        Optionally filters by UUID match (endpoint or workspace) or partial
        text match on URL / workspace slug / workspace name.  Results are
        ordered by creation date descending.
        """
        stmt = (
            self.get_base_statement()
            .join(Workspace, WebhookEndpoint.workspace_id == Workspace.id)
            .options(contains_eager(WebhookEndpoint.workspace))
            .order_by(WebhookEndpoint.created_at.desc())
        )

        if query:
            try:
                q_uuid = uuid.UUID(query)
                stmt = stmt.where(
                    or_(
                        WebhookEndpoint.id == q_uuid,
                        WebhookEndpoint.workspace_id == q_uuid,
                    )
                )
            except ValueError:
                escaped = escape_like(query)
                stmt = stmt.where(
                    or_(
                        WebhookEndpoint.url.ilike(f"%{escaped}%"),
                        Workspace.slug.ilike(f"%{escaped}%"),
                        Workspace.name.ilike(f"%{escaped}%"),
                    )
                )

        return stmt
