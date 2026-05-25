"""A federated 3D model uploaded to a project — the viewer chamber's
root entity.

Lifecycle: ``uploaded`` after the multipart upload completes →
``parsing`` once the IfcOpenShell worker starts → ``ready`` after the
XKT (xeokit's optimised format) is in S3 and the metadata fields are
populated → ``failed`` if any step throws.

The actual IfcOpenShell subprocess body ships in M3.1b (this PR is
the scaffold). Workers fail with a NotImplemented status code until
that lands; the rows + routes + permissions exist so the frontend
upload UI can be built against a real surface.
"""

from enum import StrEnum
from typing import TYPE_CHECKING, Any
from uuid import UUID

from sqlalchemy import ForeignKey, Integer, String, Text, Uuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, declared_attr, mapped_column, relationship

from rapidly.core.db.models import BaseEntity
from rapidly.core.extensions.sqlalchemy import StringEnum

if TYPE_CHECKING:
    from .file import File
    from .project import Project


class ModelStatus(StrEnum):
    """Lifecycle of a federated model from upload through parse."""

    uploaded = "uploaded"
    parsing = "parsing"
    ready = "ready"
    failed = "failed"


class FederatedModel(BaseEntity):
    """A 3D model (IFC + derived XKT) attached to a project.

    Soft-delete is provided by ``BaseEntity.deleted_at``; the
    repository's ``SoftDeleteMixin`` filters those rows out by default.
    """

    __tablename__ = "federated_models"

    project_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("projects.id", ondelete="cascade"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(256), nullable=False)

    # Source IFC (or GLB, etc.) — uploaded via the existing
    # catalog/file presigned-PUT flow.
    source_file_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("files.id", ondelete="restrict"),
        nullable=False,
        index=True,
    )
    # Worker-produced XKT (xeokit's optimised viewer format).
    # Nullable until status='ready'.
    xkt_file_id: Mapped[UUID | None] = mapped_column(
        Uuid,
        ForeignKey("files.id", ondelete="set null"),
        nullable=True,
        index=True,
    )

    status: Mapped[ModelStatus] = mapped_column(
        StringEnum(ModelStatus, length=16),
        nullable=False,
        default=ModelStatus.uploaded,
    )
    # Worker output: units (mm/m/ft/in), element count, world bbox.
    # All nullable until the worker fills them in.
    units: Mapped[str | None] = mapped_column(String(8), nullable=True)
    element_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    bbox: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)

    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    @declared_attr
    def project(cls) -> Mapped["Project"]:
        return relationship("Project", lazy="raise")

    @declared_attr
    def source_file(cls) -> Mapped["File"]:
        return relationship("File", foreign_keys=[cls.source_file_id], lazy="raise")

    @declared_attr
    def xkt_file(cls) -> Mapped["File | None"]:
        return relationship("File", foreign_keys=[cls.xkt_file_id], lazy="raise")
