"""Admin customer query repository.

Centralises direct DB access for the admin customers module, following the
convention that API handlers never execute raw ``select()`` /
``session.execute()`` calls themselves.
"""

from __future__ import annotations

import uuid

from sqlalchemy import Select, func, or_
from sqlalchemy.orm import contains_eager

from rapidly.core.queries import Repository
from rapidly.core.queries.utils import escape_like
from rapidly.models import Customer, Workspace


class AdminCustomerRepository(Repository[Customer]):
    """Admin-specific queries for the customer list view."""

    model = Customer

    def get_list_statement(
        self,
        *,
        query: str | None = None,
    ) -> Select[tuple[Customer]]:
        """Return a statement for listing customers with workspace eagerly loaded.

        Optionally filters by UUID match (customer or workspace) or
        case-insensitive partial text match on email / name / external_id /
        workspace slug / workspace name.  Results are ordered by creation
        date descending.
        """
        stmt = (
            self.get_base_statement()
            .join(Workspace, Customer.workspace_id == Workspace.id)
            .options(contains_eager(Customer.workspace))
        )

        if query is not None:
            try:
                parsed_uuid = uuid.UUID(query)
                stmt = stmt.where(
                    or_(
                        Customer.id == parsed_uuid,
                        Workspace.id == parsed_uuid,
                    )
                )
            except ValueError:
                escaped = escape_like(query.lower())
                stmt = stmt.where(
                    or_(
                        func.lower(Customer.email).ilike(f"%{escaped}%"),
                        func.lower(Customer.name).ilike(f"%{escaped}%"),
                        func.lower(Customer.external_id).ilike(f"%{escaped}%"),
                        func.lower(Workspace.slug).ilike(f"%{escaped}%"),
                        func.lower(Workspace.name).ilike(f"%{escaped}%"),
                    )
                )

        stmt = stmt.order_by(Customer.created_at.desc())
        return stmt
