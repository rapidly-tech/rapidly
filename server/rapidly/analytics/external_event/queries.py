"""External-event persistence layer.

``ExternalEventRepository`` handles raw third-party webhook payloads
(Stripe, GitHub, etc.) that arrive before normalisation into the
internal analytics pipeline.  Supports source-based lookups,
unhandled-event polling, and time-based cleanup.
"""

from collections.abc import Sequence
from datetime import datetime
from uuid import UUID

from sqlalchemy import delete

from rapidly.core.queries import (
    FindByIdMixin,
    Repository,
    SortableMixin,
    SortingClause,
)
from rapidly.models.external_event import ExternalEvent, ExternalEventSource

from .ordering import ExternalEventSortProperty


class ExternalEventRepository(
    SortableMixin[ExternalEvent, ExternalEventSortProperty],
    Repository[ExternalEvent],
    FindByIdMixin[ExternalEvent, UUID],
):
    """Source-filtered lookups, unhandled polling, and TTL-based purge."""

    model = ExternalEvent

    # ------------------------------------------------------------------
    # Lookups
    # ------------------------------------------------------------------

    async def get_by_source_and_id(
        self,
        source: ExternalEventSource,
        id: UUID,
        *,
        with_for_update: bool = False,
    ) -> ExternalEvent | None:
        stmt = self.get_base_statement().where(
            ExternalEvent.source == source, ExternalEvent.id == id
        )
        if with_for_update:
            stmt = stmt.with_for_update()
        return await self.get_one_or_none(stmt)

    async def get_by_source_and_external_id(
        self, source: ExternalEventSource, external_id: str
    ) -> ExternalEvent | None:
        stmt = self.get_base_statement().where(
            ExternalEvent.source == source, ExternalEvent.external_id == external_id
        )
        return await self.get_one_or_none(stmt)

    # ------------------------------------------------------------------
    # Polling & cleanup
    # ------------------------------------------------------------------

    async def get_all_unhandled(
        self, older_than: datetime | None = None
    ) -> Sequence[ExternalEvent]:
        stmt = self.get_base_statement().where(ExternalEvent.handled_at.is_(None))
        if older_than is not None:
            stmt = stmt.where(ExternalEvent.created_at < older_than)
        return await self.get_all(stmt)

    async def delete_before(self, before: datetime) -> None:
        stmt = delete(ExternalEvent).where(
            ExternalEvent.handled_at.is_not(None),
            ExternalEvent.created_at < before,
        )
        await self.session.execute(stmt)

    # ------------------------------------------------------------------
    # Sorting
    # ------------------------------------------------------------------

    def get_sorting_clause(self, property: ExternalEventSortProperty) -> SortingClause:
        match property:
            case ExternalEventSortProperty.created_at:
                return self.model.created_at
            case ExternalEventSortProperty.handled_at:
                return self.model.handled_at
            case ExternalEventSortProperty.source:
                return self.model.source
            case ExternalEventSortProperty.task_name:
                return self.model.task_name
