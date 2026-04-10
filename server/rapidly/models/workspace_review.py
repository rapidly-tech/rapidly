"""ORM model for workspace verification and review workflows."""

from datetime import UTC, datetime
from enum import StrEnum
from typing import TYPE_CHECKING, Any
from uuid import UUID

from sqlalchemy import TIMESTAMP, ForeignKey, String, Text, Uuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, declared_attr, mapped_column, relationship

from rapidly.core.db.models import BaseEntity

if TYPE_CHECKING:
    from rapidly.models.workspace import Workspace


class WorkspaceReview(BaseEntity):
    """Model to store AI validation responses for workspaces."""

    class Verdict(StrEnum):
        PASS = "PASS"
        FAIL = "FAIL"
        UNCERTAIN = "UNCERTAIN"

    class AppealDecision(StrEnum):
        APPROVED = "approved"
        REJECTED = "rejected"

    __tablename__ = "workspace_reviews"

    workspace_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("workspaces.id", ondelete="cascade"),
        nullable=False,
        unique=True,
        index=True,
    )

    verdict: Mapped[Verdict] = mapped_column(String, nullable=False)
    risk_score: Mapped[float] = mapped_column(nullable=False)
    violated_sections: Mapped[list[str]] = mapped_column(
        JSONB, nullable=False, default=list
    )
    reason: Mapped[str] = mapped_column(Text, nullable=False)

    timed_out: Mapped[bool] = mapped_column(nullable=False, default=False)
    model_used: Mapped[str] = mapped_column(String, nullable=False)

    workspace_details_snapshot: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict
    )

    validated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )

    # Appeal fields
    appeal_submitted_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True, default=None
    )
    appeal_reason: Mapped[str | None] = mapped_column(Text, nullable=True, default=None)
    appeal_reviewed_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True, default=None
    )
    appeal_decision: Mapped[AppealDecision | None] = mapped_column(
        String, nullable=True, default=None
    )

    @declared_attr
    def workspace(cls) -> Mapped["Workspace"]:
        return relationship("Workspace", lazy="raise", back_populates="review")

    def __repr__(self) -> str:
        return f"WorkspaceReview(id={self.id}, workspace_id={self.workspace_id}, verdict={self.verdict})"
