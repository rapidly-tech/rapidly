"""Dataset of input/expected-output pairs used to evaluate workflows.

A Dataset belongs to a workspace and groups N ``DatasetCase``
rows, each holding one input_data + (optional) expected_output
fixture. The eval runner (M4.8b) drives a workflow against
every case in the dataset and compares actual vs expected.

Why Dataset is a first-class model (not a JSON blob on Workflow):
    A dataset is reusable across workflows + workflow versions
    (the "did my edit improve recall?" question needs the same
    fixture against two versions). Modeling it separately also
    lets the API surface CRUD on individual cases without
    rewriting the whole blob.

Why no workflow_id FK:
    A dataset can be applied to any workflow whose input shape
    matches its cases. Pinning to one workflow would force a
    duplicate dataset for every fork or rename.
"""

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, String, Text, Uuid
from sqlalchemy.orm import Mapped, declared_attr, mapped_column, relationship

from rapidly.core.db.models.base import BaseEntity

if TYPE_CHECKING:
    from .workspace import Workspace


class Dataset(BaseEntity):
    """A named bundle of test cases for workflow evaluation."""

    __tablename__ = "agent_datasets"

    workspace_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("workspaces.id", ondelete="cascade"),
        nullable=False,
        index=True,
    )

    name: Mapped[str] = mapped_column(String(256), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Archive (separate from soft-delete). Mirrors the workflow
    # archive shape (M5.65): operators stash a dataset they're
    # no longer using without losing it, and past eval-runs still
    # resolve their parent dataset by id.
    archived_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
    )

    @declared_attr
    def workspace(cls) -> Mapped["Workspace"]:
        return relationship("Workspace", lazy="raise")
