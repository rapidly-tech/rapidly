"""Public-board configuration for a project.

A ``ProjectDeployBoard`` captures the *settings* that govern a public
read-only view of a project: which sub-surfaces are exposed (work
items, comments, votes, reactions), what the token-secured public
URL is, and which display defaults the unauthenticated reader sees.

This PR ships the **configuration layer only**.  The actual
anonymous-read endpoints (``GET /public-project-boards/{token}`` and
the work-item/comment surfaces it exposes) are a separate PR because
their security envelope — what gets surfaced anonymously, what's
filtered, how rate limits apply — deserves its own spec.

One deploy board per project (unique ``project_id``).  Admins
manage the row; a board's existence doesn't imply the project is
public — the ``is_public`` flag is the actual switch and defaults
to ``False`` so creating a board is a safe staging move.
"""

from typing import TYPE_CHECKING, Any
from uuid import UUID

from sqlalchemy import (
    Boolean,
    ForeignKey,
    String,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, declared_attr, mapped_column, relationship

from rapidly.core.db.models import BaseEntity

if TYPE_CHECKING:
    from .project import Project


class ProjectDeployBoard(BaseEntity):
    """Public-board config for one project."""

    __tablename__ = "project_deploy_boards"
    __table_args__ = (
        UniqueConstraint("project_id", name="project_deploy_boards_project_id_key"),
        # Token uniqueness lets us look up by token in O(1) and rejects
        # collisions if random generation ever clashes.
        UniqueConstraint("token", name="project_deploy_boards_token_key"),
    )

    project_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("projects.id", ondelete="cascade"),
        nullable=False,
        index=True,
    )

    # Secret nonce. The public URL is built from this — anyone with
    # the URL gets read access while ``is_public`` is true.  The
    # action layer regenerates this on demand so admins can revoke
    # a compromised link.
    token: Mapped[str] = mapped_column(String(64), nullable=False)

    # Master kill switch. The token is meaningless when this is False;
    # callers can pre-stage view_props before going public.
    is_public: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # Per-surface toggles. All default off so making a board public
    # exposes only the work-item list; comments / reactions / votes /
    # the intake form each require an explicit opt-in.
    show_comments: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    show_reactions: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    show_votes: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    show_intake_form: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )

    # Opaque JSON. Layout choice, default filters, theme colours —
    # owned by the frontend, evolves without migrations.
    view_props: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict
    )

    @declared_attr
    def project(cls) -> Mapped["Project"]:
        return relationship("Project", lazy="raise")
