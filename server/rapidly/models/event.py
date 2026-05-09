"""Telemetry event model with closure-table hierarchy.

Events are the core observability primitive.  Each records a named
occurrence for a customer or member within a workspace.  A closure
table (``EventClosure``) maintains ancestor/descendant pairs so
sub-event trees can be queried in a single round-trip.

The ``CustomerComparator`` and ``MemberComparator`` classes allow
SQLAlchemy relationship operators (``==``, ``is_``, ``is_not``) to
transparently resolve events by both internal ID and external ID.
"""

import datetime
from enum import StrEnum
from typing import TYPE_CHECKING, Any, cast
from uuid import UUID

from sqlalchemy import (
    TIMESTAMP,
    BigInteger,
    ColumnElement,
    ForeignKey,
    Index,
    Select,
    String,
    Uuid,
    and_,
    case,
    event,
    exists,
    extract,
    literal_column,
    or_,
    select,
    update,
)
from sqlalchemy import (
    cast as sql_cast,
)
from sqlalchemy import (
    cast as sqla_cast,
)
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import (
    Mapped,
    Relationship,
    column_property,
    declared_attr,
    mapped_column,
    relationship,
)
from sqlalchemy.sql.elements import BinaryExpression

from rapidly.core.db.models import Model
from rapidly.core.metadata import MetadataMixin, get_nested_metadata_value
from rapidly.core.utils import create_uuid, now_utc

from .customer import Customer
from .member import Member

if TYPE_CHECKING:
    from .event_type import EventType
    from .workspace import Workspace

# Upper bound for the ``name`` column.
_NAME_MAX_LEN: int = 128

# Internal system event name for meter credit entries.
_METER_CREDIT_EVENT_NAME: str = "meter.credited"


# -- Source discriminator ----------------------------------------------------


class EventSource(StrEnum):
    """Whether the event was generated internally or by user code."""

    system = "system"
    user = "user"


# -- Relationship comparators -----------------------------------------------
#
# These let SQLAlchemy relationship expressions transparently match on
# both the internal UUID FK and the external string ID, enabling
# queries like ``Event.customer == some_customer``.


class CustomerComparator(Relationship.Comparator[Customer]):
    """Matches events to a customer by internal or external ID."""

    def __eq__(self, other: Any) -> ColumnElement[bool]:  # type: ignore[override]
        if isinstance(other, Customer):
            by_id = Event.customer_id == other.id
            if other.external_id is not None:
                return or_(
                    by_id,
                    and_(
                        Event.external_customer_id.is_not(None),
                        Event.external_customer_id == other.external_id,
                        Event.workspace_id == other.workspace_id,
                    ),
                )
            return by_id
        raise NotImplementedError()

    def is_(self, other: Any) -> BinaryExpression[bool]:
        if other is None:
            return cast(
                BinaryExpression[bool],
                and_(
                    Event.customer_id.is_(None),
                    or_(
                        Event.external_customer_id.is_(None),
                        ~exists(
                            select(1).where(
                                Customer.external_id == Event.external_customer_id,
                                Customer.workspace_id == Event.workspace_id,
                            )
                        ),
                    ),
                ),
            )
        raise NotImplementedError()

    def is_not(self, other: Any) -> BinaryExpression[bool]:
        if other is None:
            return cast(
                BinaryExpression[bool],
                or_(
                    Event.customer_id.is_not(None),
                    and_(
                        Event.external_customer_id.is_not(None),
                        exists(
                            select(1).where(
                                Customer.external_id == Event.external_customer_id,
                                Customer.workspace_id == Event.workspace_id,
                            )
                        ),
                    ),
                ),
            )
        raise NotImplementedError()


class MemberComparator(Relationship.Comparator[Member]):
    """Matches events to a member by internal or external ID."""

    def __eq__(self, other: Any) -> ColumnElement[bool]:  # type: ignore[override]
        if isinstance(other, Member):
            by_id = Event.member_id == other.id
            if other.external_id is not None:
                return or_(
                    by_id,
                    and_(
                        Event.external_member_id.is_not(None),
                        Event.external_member_id == other.external_id,
                        Event.workspace_id == other.workspace_id,
                    ),
                )
            return by_id
        raise NotImplementedError()

    def is_(self, other: Any) -> BinaryExpression[bool]:
        if other is None:
            return cast(
                BinaryExpression[bool],
                and_(
                    Event.member_id.is_(None),
                    or_(
                        Event.external_member_id.is_(None),
                        ~exists(
                            select(1).where(
                                Member.external_id == Event.external_member_id,
                                Member.workspace_id == Event.workspace_id,
                            )
                        ),
                    ),
                ),
            )
        raise NotImplementedError()

    def is_not(self, other: Any) -> BinaryExpression[bool]:
        if other is None:
            return cast(
                BinaryExpression[bool],
                or_(
                    Event.member_id.is_not(None),
                    and_(
                        Event.external_member_id.is_not(None),
                        exists(
                            select(1).where(
                                Member.external_id == Event.external_member_id,
                                Member.workspace_id == Event.workspace_id,
                            )
                        ),
                    ),
                ),
            )
        raise NotImplementedError()


# -- Event model -------------------------------------------------------------


class Event(Model, MetadataMixin):
    """A single telemetry occurrence with optional parent/root linkage."""

    __tablename__ = "events"
    __table_args__ = (
        Index(
            "ix_events_org_timestamp_id",
            literal_column("timestamp DESC"),
            "id",
        ),
        Index(
            "ix_events_workspace_external_id_ingested_at_desc",
            "external_customer_id",
            literal_column("ingested_at DESC"),
        ),
        Index(
            "ix_events_workspace_customer_id_ingested_at_desc",
            "customer_id",
            literal_column("ingested_at DESC"),
        ),
        Index(
            "ix_events_external_customer_id_pattern",
            "external_customer_id",
            postgresql_ops={"external_customer_id": "text_pattern_ops"},
        ),
        Index(
            "ix_events_workspace_id_source_id",
            "source",
            "id",
        ),
        Index(
            "ix_events_workspace_id_external_id",
            "external_id",
            unique=True,
        ),
        Index(
            "ix_events_org_source_name_external_customer_id_ingested_at",
            "source",
            "name",
            "external_customer_id",
            literal_column("ingested_at DESC"),
            postgresql_where="external_customer_id IS NOT NULL",
        ),
        Index(
            "ix_events_org_source_name_customer_id_ingested_at",
            "source",
            "name",
            "customer_id",
            literal_column("ingested_at DESC"),
            postgresql_where="customer_id IS NOT NULL",
        ),
    )

    # -- Primary key ---------------------------------------------------------

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=create_uuid)

    # -- Timestamps ----------------------------------------------------------

    ingested_at: Mapped[datetime.datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, default=now_utc, index=True
    )
    timestamp: Mapped[datetime.datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, default=now_utc, index=True
    )

    # -- Event identity ------------------------------------------------------

    name: Mapped[str] = mapped_column(String(_NAME_MAX_LEN), nullable=False, index=True)
    source: Mapped[EventSource] = mapped_column(
        String, nullable=False, default=EventSource.system, index=True
    )
    external_id: Mapped[str | None] = mapped_column(String, nullable=True)

    # -- Customer association (internal + external) --------------------------

    customer_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("customers.id", ondelete="set null"), nullable=True, index=True
    )
    external_customer_id: Mapped[str | None] = mapped_column(
        String, nullable=True, index=True
    )

    @declared_attr
    def customer(cls) -> Mapped[Customer | None]:
        return relationship(
            Customer,
            primaryjoin=(
                "or_("
                "Event.customer_id == Customer.id,"
                "and_("
                "Event.external_customer_id == Customer.external_id,"
                "Event.workspace_id == Customer.workspace_id"
                ")"
                ")"
            ),
            comparator_factory=CustomerComparator,
            lazy="raise",
            viewonly=True,
        )

    resolved_customer_id: Mapped[UUID | str] = column_property(
        case(
            (customer_id.is_not(None), sql_cast(customer_id, String)),
            else_=external_customer_id,
        )
    )

    # -- Member association (internal + external) ----------------------------

    member_id: Mapped[UUID | None] = mapped_column(
        Uuid,
        nullable=True,
        index=True,
    )
    external_member_id: Mapped[str | None] = mapped_column(String, nullable=True)

    @declared_attr
    def member(cls) -> Mapped[Member | None]:
        return relationship(
            Member,
            primaryjoin=(
                "or_("
                "foreign(Event.member_id) == Member.id,"
                "and_("
                "foreign(Event.external_member_id) == Member.external_id,"
                "Event.workspace_id == Member.workspace_id"
                ")"
                ")"
            ),
            comparator_factory=MemberComparator,
            lazy="raise",
            viewonly=True,
        )

    resolved_member_id: Mapped[UUID | str | None] = column_property(
        case(
            (member_id.is_not(None), sql_cast(member_id, String)),
            else_=external_member_id,
        )
    )

    # -- Hierarchy -----------------------------------------------------------

    parent_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("events.id", ondelete="set null"), nullable=True, index=True
    )
    root_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("events.id", ondelete="set null"), nullable=True, index=True
    )

    @declared_attr
    def parent(cls) -> Mapped["Event | None"]:
        return relationship(
            "Event",
            foreign_keys="Event.parent_id",
            remote_side="Event.id",
            lazy="raise",
        )

    # -- Workspace -----------------------------------------------------------

    workspace_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("workspaces.id", ondelete="cascade"),
        nullable=False,
        index=True,
    )

    @declared_attr
    def workspace(cls) -> Mapped["Workspace"]:
        return relationship("Workspace", lazy="raise")

    # -- Event type ----------------------------------------------------------

    event_type_id: Mapped[UUID | None] = mapped_column(
        Uuid,
        ForeignKey("event_types.id", ondelete="set null"),
        nullable=True,
        index=True,
    )

    @declared_attr
    def event_types(cls) -> Mapped["EventType | None"]:
        return relationship("EventType", lazy="raise")

    # -- Display label -------------------------------------------------------

    @property
    def label(self) -> str:
        """Human-readable label, resolved from system labels or event type."""
        if self.source == EventSource.system:
            from rapidly.analytics.event.system import SYSTEM_EVENT_LABELS

            return SYSTEM_EVENT_LABELS.get(self.name, self.name)

        if self.event_types is not None:
            base = self.event_types.label
            if self.event_types.label_property_selector:
                dynamic = get_nested_metadata_value(
                    self.user_metadata, self.event_types.label_property_selector
                )
                if dynamic:
                    return str(dynamic)
            return base

        return self.name

    # -- Meter credit detection ----------------------------------------------

    @hybrid_property
    def is_meter_credit(self) -> bool:
        return (
            self.source == EventSource.system and self.name == _METER_CREDIT_EVENT_NAME
        )

    @is_meter_credit.inplace.expression
    @classmethod
    def _is_meter_credit_expression(cls) -> ColumnElement[bool]:
        return and_(
            cls.source == EventSource.system,
            cls.name == _METER_CREDIT_EVENT_NAME,
        )

    # -- Filterable field registry -------------------------------------------

    _filterable_fields: dict[str, tuple[type[str | int | bool], Any]] = {
        "timestamp": (int, sqla_cast(extract("epoch", timestamp), BigInteger)),
        "name": (str, name),
        "source": (str, source),
    }


# -- Closure table -----------------------------------------------------------


class EventClosure(Model):
    """Materialised ancestor-descendant pairs for the event hierarchy."""

    __tablename__ = "events_closure"
    __table_args__ = (
        Index(
            "ix_events_closure_ancestor_descendant",
            "ancestor_id",
            "descendant_id",
        ),
        Index(
            "ix_events_closure_descendant_ancestor",
            "descendant_id",
            "ancestor_id",
        ),
    )

    ancestor_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("events.id", ondelete="cascade"),
        primary_key=True,
        nullable=False,
    )
    descendant_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("events.id", ondelete="cascade"),
        primary_key=True,
        nullable=False,
    )
    depth: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)

    @declared_attr
    def ancestor(cls) -> Mapped[Event]:
        return relationship(
            Event,
            foreign_keys="EventClosure.ancestor_id",
            lazy="raise",
        )

    @declared_attr
    def descendant(cls) -> Mapped[Event]:
        return relationship(
            Event,
            foreign_keys="EventClosure.descendant_id",
            lazy="raise",
        )


# -- After-insert hook: maintain closure table -------------------------------


@event.listens_for(Event, "after_insert")
def populate_event_closure(mapper: Any, connection: Any, target: Event) -> None:
    """Keep the closure table in sync after every event insert.

    Steps:
    1. Insert the self-reference row (depth 0).
    2. Copy parent's ancestor rows with incremented depth.
    3. Back-fill ``root_id`` for the new sub-tree.
    """
    # 1. Self-reference
    connection.execute(
        insert(EventClosure).values(
            ancestor_id=target.id,
            descendant_id=target.id,
            depth=0,
        )
    )

    # 2. Propagate parent closure
    if target.parent_id is not None:
        parent_rows: Select[Any] = select(
            EventClosure.ancestor_id,
            literal_column(f"'{target.id}'::uuid").label("descendant_id"),
            (EventClosure.depth + 1).label("depth"),
        ).where(EventClosure.descendant_id == target.parent_id)

        connection.execute(
            insert(EventClosure).from_select(
                ["ancestor_id", "descendant_id", "depth"],
                parent_rows,
            )
        )

    # 3. Resolve root_id
    if target.root_id is None:
        if target.parent_id is None:
            connection.execute(
                update(Event).where(Event.id == target.id).values(root_id=target.id)
            )
            target.root_id = target.id
        else:
            result = connection.execute(
                select(Event.root_id).where(Event.id == target.parent_id)
            )
            parent_root = result.scalar_one_or_none()
            resolved_root = parent_root or target.parent_id
            connection.execute(
                update(Event).where(Event.id == target.id).values(root_id=resolved_root)
            )
            target.root_id = resolved_root
