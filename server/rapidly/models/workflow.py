"""A workflow — the agent runtime's root authoring entity.

A Workflow is the mutable shell. Its actual graph_json lives on
``WorkflowVersion`` rows (immutable snapshots), and execution
records live on ``Run`` + ``NodeRun`` (also immutable). Splitting
the mutable shell from the snapshot history lets the runtime
target a specific version when starting a run — a workflow that's
been edited mid-execution doesn't change what the in-flight Run
sees.

``project_id`` is nullable so a workflow can live at the workspace
level (cross-project, e.g. "tag all incoming RFIs with a discipline"
running on every project's RFI inbox). Most workflows will pin to a
project for tenancy clarity.

Versions, runs, and node-runs ship in follow-up PRs alongside their
own submodules. M4.1a scaffolds the root entity + its CRUD only.
"""

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, String, Text, Uuid
from sqlalchemy.orm import Mapped, declared_attr, mapped_column, relationship

from rapidly.core.db.models import BaseEntity

if TYPE_CHECKING:
    from .project import Project
    from .workspace import Workspace


class Workflow(BaseEntity):
    """An agent workflow owned by a workspace and optionally a project.

    Soft-delete via ``BaseEntity.deleted_at`` — archived workflows
    stay queryable so a Run history can still resolve its parent
    name.
    """

    __tablename__ = "workflows"

    workspace_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("workspaces.id", ondelete="cascade"),
        nullable=False,
        index=True,
    )
    # Nullable: workspace-level workflows. The common case will pin
    # to a project for tenancy clarity but the runtime allows both.
    project_id: Mapped[UUID | None] = mapped_column(
        Uuid,
        ForeignKey("projects.id", ondelete="cascade"),
        nullable=True,
        index=True,
    )

    name: Mapped[str] = mapped_column(String(256), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # FK to the active version. Nullable for the just-created state
    # (the editor will POST /versions to publish the first version
    # and then PATCH this column).
    #
    # Lives as a nullable FK rather than a derived "latest version"
    # query because the active-version may be pinned to an older row
    # while editing happens against a draft (the editor's "publish"
    # button flips this).
    current_version_id: Mapped[UUID | None] = mapped_column(
        Uuid,
        # No ForeignKey constraint here yet — the workflow_versions
        # table is defined in a sibling migration; the FK is added
        # then. Leaving it untyped at the SQL level keeps the
        # migrations linearisable.
        nullable=True,
        index=True,
    )

    # Archive (separate from soft-delete). Operators archive a
    # workflow they want to stash without losing — past runs and
    # versions stay queryable, but the workflows list hides it
    # by default. Soft-delete (deleted_at) is the destructive
    # path; archive is the "keep but tuck away" path.
    archived_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
    )

    @declared_attr
    def workspace(cls) -> Mapped["Workspace"]:
        return relationship("Workspace", lazy="raise")

    @declared_attr
    def project(cls) -> Mapped["Project | None"]:
        return relationship("Project", lazy="raise")
