"""An immutable snapshot of a Workflow's graph_json.

WorkflowVersion is append-only: once a version is published the row
never mutates. The Workflow row's ``current_version_id`` points at
the version the runtime targets by default; switching it is a
PATCH on the Workflow (one column update), not an edit on a version.

Why separate from Workflow:
- Runs target a specific WorkflowVersion. A workflow that's been
  edited mid-run doesn't affect what the in-flight Run sees.
- Append-only snapshots give a free audit trail of what shipped
  when, by whom.
- Rollback is "set current_version_id back to <older.id>" — one
  UPDATE, no graph manipulation.

Schema notes:
- ``version_number`` is per-workflow monotonically increasing; the
  unique constraint enforces uniqueness within a workflow.
- ``graph_json`` is the editor's serialised graph (nodes + edges).
  Shape lives in the API types module + the M5 frontend.
- No soft-delete: snapshots are forever. Deleting a Workflow
  cascades to its versions.
"""

from typing import TYPE_CHECKING, Any
from uuid import UUID

from sqlalchemy import ForeignKey, Integer, UniqueConstraint, Uuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, declared_attr, mapped_column, relationship

from rapidly.core.db.models import BaseEntity

if TYPE_CHECKING:
    from .user import User
    from .workflow import Workflow


class WorkflowVersion(BaseEntity):
    """An immutable snapshot of a workflow's graph_json."""

    __tablename__ = "workflow_versions"
    __table_args__ = (
        UniqueConstraint(
            "workflow_id",
            "version_number",
            name="uq_workflow_versions_workflow_version",
        ),
    )

    workflow_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("workflows.id", ondelete="cascade"),
        nullable=False,
        index=True,
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    # The editor's serialised graph: ``{ nodes: [...], edges: [...] }``.
    # Schema validation lives at the API boundary (types.py); the DB
    # only stores the blob so a future graph-schema evolution doesn't
    # require a column-shape migration.
    graph_json: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict
    )
    created_by_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("users.id", ondelete="restrict"),
        nullable=False,
        index=True,
    )

    @declared_attr
    def workflow(cls) -> Mapped["Workflow"]:
        return relationship("Workflow", lazy="raise")

    @declared_attr
    def created_by(cls) -> Mapped["User"]:
        return relationship("User", lazy="raise")
