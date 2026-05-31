"""Directed relation between two work items inside the same project.

Each relation carries a typed verb (``blocks``, ``relates_to``,
``duplicates``).  Inverse semantics (``is_blocked_by``,
``duplicated_by``) are derived at read time from the source row —
storing the inverse explicitly would double-write every link and
risk drift.

Constraints enforced at the DB level:

- ``UNIQUE(work_item_id, related_id, relation_type)`` — no duplicate
  edges of the same type.
- ``CHECK(work_item_id != related_id)`` — a work item cannot relate
  to itself.

Cross-project relations are blocked in the action layer, not the
schema — a project might one day allow them (e.g. epic-spanning).
"""

from enum import StrEnum
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import CheckConstraint, ForeignKey, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, declared_attr, mapped_column, relationship

from rapidly.core.db.models import BaseEntity
from rapidly.core.extensions.sqlalchemy import StringEnum

if TYPE_CHECKING:
    from .work_item import WorkItem


class WorkItemRelationType(StrEnum):
    """Directed relation verbs.  Inverses derived at read time."""

    blocks = "blocks"
    relates_to = "relates_to"
    duplicates = "duplicates"


class WorkItemRelation(BaseEntity):
    """A typed edge from ``work_item_id`` → ``related_id``."""

    __tablename__ = "work_item_relations"
    __table_args__ = (
        UniqueConstraint(
            "work_item_id",
            "related_id",
            "relation_type",
            name="work_item_relations_work_item_id_related_id_relation_type_key",
        ),
        CheckConstraint(
            "work_item_id <> related_id",
            name="work_item_relations_no_self_link_check",
        ),
    )

    work_item_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("work_items.id", ondelete="cascade"),
        nullable=False,
        index=True,
    )
    related_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("work_items.id", ondelete="cascade"),
        nullable=False,
        index=True,
    )
    relation_type: Mapped[WorkItemRelationType] = mapped_column(
        StringEnum(WorkItemRelationType, length=16), nullable=False
    )

    @declared_attr
    def work_item(cls) -> Mapped["WorkItem"]:
        return relationship(
            "WorkItem", foreign_keys="WorkItemRelation.work_item_id", lazy="raise"
        )

    @declared_attr
    def related(cls) -> Mapped["WorkItem"]:
        return relationship(
            "WorkItem", foreign_keys="WorkItemRelation.related_id", lazy="raise"
        )
