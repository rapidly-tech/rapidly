"""Admin file-sharing query repository.

Centralises direct DB access for the admin file-sharing module, following
the convention that API handlers never execute raw ``select()`` /
``session.execute()`` calls themselves.
"""

from __future__ import annotations

from sqlalchemy import Select, or_

from rapidly.core.queries import Repository
from rapidly.core.queries.utils import escape_like
from rapidly.models.file_share_session import FileShareSession, FileShareSessionStatus


class AdminFileShareSessionRepository(Repository[FileShareSession]):
    """Admin-specific queries for the file-sharing session list view."""

    model = FileShareSession

    def get_list_statement(
        self,
        *,
        query: str | None = None,
        status: str | None = None,
    ) -> Select[tuple[FileShareSession]]:
        """Return a filterable statement for listing file-sharing sessions.

        Optionally filters by:
        - Partial text match on ``short_slug``, ``long_slug``, or ``file_name``
        - Session status enum value
        """
        stmt = self.get_base_statement()

        if query:
            escaped = escape_like(query)
            stmt = stmt.where(
                or_(
                    FileShareSession.short_slug.ilike(f"%{escaped}%"),
                    FileShareSession.long_slug.ilike(f"%{escaped}%"),
                    FileShareSession.file_name.ilike(f"%{escaped}%"),
                )
            )

        if status:
            try:
                status_enum = FileShareSessionStatus(status)
                stmt = stmt.where(FileShareSession.status == status_enum)
            except ValueError:
                pass

        return stmt
