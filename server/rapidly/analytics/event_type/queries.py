"""Event-type persistence layer with slug-based look-up.

``EventTypeRepository`` manages the catalogue of named event types per
workspace, enforcing unique slugs and supporting soft-delete with
timestamp tracking.
"""

from datetime import datetime
from uuid import UUID

from sqlalchemy import Select, func, select
from sqlalchemy.exc import IntegrityError

from rapidly.core.queries import FindByIdMixin, Repository
from rapidly.identity.auth.models import (
    AuthPrincipal,
    User,
    Workspace,
    is_user_principal,
    is_workspace_principal,
)
from rapidly.models import Event, EventType, WorkspaceMembership
from rapidly.models.event import EventSource


class EventTypeRepository(Repository[EventType], FindByIdMixin[EventType, UUID]):
    """Event-type catalogue queries with occurrence stats and name-based bulk lookups."""

    model = EventType

    # ── Reads ──

    def get_readable_statement(
        self, auth_subject: AuthPrincipal[User | Workspace]
    ) -> Select[tuple[EventType]]:
        statement = self.get_base_statement()

        if is_user_principal(auth_subject):
            user = auth_subject.subject
            statement = statement.where(
                EventType.workspace_id.in_(
                    select(WorkspaceMembership.workspace_id).where(
                        WorkspaceMembership.user_id == user.id,
                        WorkspaceMembership.deleted_at.is_(None),
                    )
                )
            )
        elif is_workspace_principal(auth_subject):
            statement = statement.where(
                EventType.workspace_id == auth_subject.subject.id
            )

        return statement

    # ── Stats queries ──

    def get_event_types_with_stats_statement(
        self, auth_subject: AuthPrincipal[User | Workspace]
    ) -> Select[tuple[EventType, EventSource, int, datetime, datetime]]:
        return (
            self.get_readable_statement(auth_subject)
            .join(Event, EventType.id == Event.event_type_id)
            .with_only_columns(
                EventType,
                Event.source,
                func.count(Event.id).label("occurrences"),
                func.min(Event.timestamp).label("first_seen"),
                func.max(Event.timestamp).label("last_seen"),
            )
            .group_by(
                EventType.id,
                EventType.created_at,
                EventType.modified_at,
                EventType.deleted_at,
                EventType.name,
                EventType.label,
                EventType.workspace_id,
                Event.source,
            )
        )

    async def get_by_name_and_workspace(
        self, name: str, workspace_id: UUID
    ) -> EventType | None:
        statement = select(EventType).where(
            EventType.name == name,
            EventType.workspace_id == workspace_id,
            EventType.deleted_at.is_(None),
        )
        result = await self.session.execute(statement)
        return result.scalar_one_or_none()

    async def get_by_names_and_workspace(
        self, names: list[str], workspace_id: UUID
    ) -> dict[str, EventType]:
        if not names:
            return {}
        statement = select(EventType).where(
            EventType.name.in_(names),
            EventType.workspace_id == workspace_id,
            EventType.deleted_at.is_(None),
        )
        result = await self.session.execute(statement)
        return {et.name: et for et in result.scalars().all()}

    async def update_label(
        self,
        event_type: EventType,
        label: str | None = None,
        label_property_selector: str | None = None,
    ) -> EventType:
        """Update an event type's label and optional property selector."""
        update_dict: dict[str, str | None] = {}
        if label is not None:
            update_dict["label"] = label
        if label_property_selector is not None:
            update_dict["label_property_selector"] = label_property_selector
        if not update_dict:
            return event_type
        return await self.update(event_type, update_dict=update_dict)

    async def get_or_create(self, name: str, workspace_id: UUID) -> EventType:
        existing = await self.get_by_name_and_workspace(name, workspace_id)
        if existing:
            return existing

        event_type = EventType(name=name, label=name, workspace_id=workspace_id)
        nested = await self.session.begin_nested()
        try:
            self.session.add(event_type)
            await self.session.flush()
        except IntegrityError:
            await nested.rollback()
            existing = await self.get_by_name_and_workspace(name, workspace_id)
            if existing:
                return existing
            raise
        return event_type
