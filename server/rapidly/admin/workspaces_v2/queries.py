"""Admin workspace query repository.

Centralises all direct DB access for the admin workspaces-v2 module,
following the project convention that API handlers never execute raw
``select()`` / ``session.execute()`` calls themselves.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import Select, and_, or_, select
from sqlalchemy.orm import joinedload

from rapidly.core.queries import Repository
from rapidly.models import Account, User, Workspace, WorkspaceMembership
from rapidly.models.user import IdentityVerificationStatus
from rapidly.models.workspace import WorkspaceStatus
from rapidly.models.workspace_review import WorkspaceReview


class AdminWorkspaceRepository(Repository[Workspace]):
    """Admin-specific workspace queries (list filtering, detail loading, etc.)."""

    model = Workspace

    # ------------------------------------------------------------------
    # List view
    # ------------------------------------------------------------------

    def build_list_statement(
        self,
        *,
        status_filter: WorkspaceStatus | None = None,
        q: str | None = None,
        country: str | None = None,
        risk_level: str | None = None,
        days_in_status_int: int | None = None,
        has_appeal: str | None = None,
        sort: str = "priority",
        direction: str = "asc",
        page: int = 1,
        limit: int = 50,
    ) -> Select[tuple[Workspace]]:
        """Build a fully-filtered, sorted, and paginated list statement."""

        stmt = select(Workspace).options(
            joinedload(Workspace.account),
            joinedload(Workspace.review),
        )

        # Status filter
        if status_filter:
            stmt = stmt.where(Workspace.status == status_filter)
        else:
            stmt = stmt.where(Workspace.status != WorkspaceStatus.DENIED)

        # Search
        if q:
            search_term = f"%{q}%"
            stmt = stmt.where(
                or_(
                    Workspace.name.ilike(search_term),
                    Workspace.slug.ilike(search_term),
                    Workspace.email.ilike(search_term),
                )
            )

        # Country filter
        if country:
            stmt = stmt.join(Workspace.account).where(Account.country == country)

        # Risk level filter
        if risk_level:
            stmt = stmt.join(Workspace.review)
            if risk_level == "high":
                stmt = stmt.where(WorkspaceReview.risk_score >= 75)
            elif risk_level == "medium":
                stmt = stmt.where(
                    WorkspaceReview.risk_score >= 50, WorkspaceReview.risk_score < 75
                )
            elif risk_level == "low":
                stmt = stmt.where(WorkspaceReview.risk_score < 50)
            elif risk_level == "unscored":
                stmt = (
                    select(Workspace)
                    .options(
                        joinedload(Workspace.account),
                        joinedload(Workspace.review),
                    )
                    .outerjoin(Workspace.review)
                    .where(WorkspaceReview.id.is_(None))
                )

        # Days in status filter
        if days_in_status_int:
            threshold_date = datetime.now(UTC) - timedelta(days=days_in_status_int)
            stmt = stmt.where(
                or_(
                    Workspace.status_updated_at <= threshold_date,
                    and_(
                        Workspace.status_updated_at.is_(None),
                        Workspace.created_at <= threshold_date,
                    ),
                )
            )

        # Appeal filter
        if has_appeal:
            stmt = stmt.join(Workspace.review)
            if has_appeal == "pending":
                stmt = stmt.where(
                    WorkspaceReview.appeal_submitted_at.is_not(None),
                    WorkspaceReview.appeal_reviewed_at.is_(None),
                )
            elif has_appeal == "reviewed":
                stmt = stmt.where(WorkspaceReview.appeal_reviewed_at.is_not(None))
            elif has_appeal == "none":
                stmt = stmt.where(WorkspaceReview.appeal_submitted_at.is_(None))

        # Sorting
        stmt = self._apply_list_sorting(stmt, sort, direction)

        # Pagination (fetch limit + 1 to detect "has more")
        offset = (page - 1) * limit
        stmt = stmt.offset(offset).limit(limit + 1)

        return stmt

    @staticmethod
    def _apply_list_sorting(
        stmt: Select[tuple[Workspace]],
        sort: str,
        direction: str,
    ) -> Select[tuple[Workspace]]:
        is_desc = direction == "desc"

        if sort == "name":
            stmt = stmt.order_by(
                Workspace.name.desc() if is_desc else Workspace.name.asc()
            )
        elif sort == "country":
            country_order = (
                Account.country.desc().nullslast()
                if is_desc
                else Account.country.asc().nullslast()
            )
            stmt = stmt.join(Workspace.account).order_by(country_order)
        elif sort == "created":
            stmt = stmt.order_by(
                Workspace.created_at.asc() if is_desc else Workspace.created_at.desc()
            )
        elif sort == "updated":
            stmt = stmt.order_by(
                Workspace.modified_at.asc() if is_desc else Workspace.modified_at.desc()
            )
        elif sort == "status_duration":
            status_order = (
                Workspace.status_updated_at.desc().nullslast()
                if is_desc
                else Workspace.status_updated_at.asc().nullsfirst()
            )
            stmt = stmt.order_by(status_order)
        elif sort == "risk":
            risk_order = (
                WorkspaceReview.risk_score.asc().nullsfirst()
                if is_desc
                else WorkspaceReview.risk_score.desc().nullslast()
            )
            stmt = stmt.join(Workspace.review).order_by(risk_order)
        elif sort == "next_review":
            threshold_order = (
                Workspace.next_review_threshold.asc().nullsfirst()
                if is_desc
                else Workspace.next_review_threshold.desc().nullslast()
            )
            stmt = stmt.order_by(threshold_order)
        elif sort == "priority":
            stmt = stmt.order_by(
                Workspace.status.desc(),
                Workspace.status_updated_at.asc().nullsfirst(),
            )

        return stmt

    async def list_workspaces(
        self,
        *,
        status_filter: WorkspaceStatus | None = None,
        q: str | None = None,
        country: str | None = None,
        risk_level: str | None = None,
        days_in_status_int: int | None = None,
        has_appeal: str | None = None,
        sort: str = "priority",
        direction: str = "asc",
        page: int = 1,
        limit: int = 50,
    ) -> tuple[list[Workspace], bool]:
        """Return ``(workspaces, has_more)`` for the admin list view."""

        stmt = self.build_list_statement(
            status_filter=status_filter,
            q=q,
            country=country,
            risk_level=risk_level,
            days_in_status_int=days_in_status_int,
            has_appeal=has_appeal,
            sort=sort,
            direction=direction,
            page=page,
            limit=limit,
        )

        result = await self.session.execute(stmt)
        workspaces = list(result.scalars().unique().all())

        has_more = len(workspaces) > limit
        if has_more:
            workspaces = workspaces[:limit]

        return workspaces, has_more

    # ------------------------------------------------------------------
    # Detail view
    # ------------------------------------------------------------------

    async def get_detail(self, workspace_id: UUID) -> Workspace | None:
        """Fetch a workspace with account and review relationships eagerly loaded."""
        stmt = (
            select(Workspace)
            .options(
                joinedload(Workspace.account),
                joinedload(Workspace.review),
            )
            .where(Workspace.id == workspace_id)
        )

        result = await self.session.execute(stmt)
        return result.scalars().unique().one_or_none()

    async def get_members(
        self, workspace_id: UUID, *, limit: int = 10
    ) -> Sequence[WorkspaceMembership]:
        """Fetch workspace memberships with user relationship loaded."""
        stmt = (
            select(WorkspaceMembership)
            .options(joinedload(WorkspaceMembership.user))
            .where(WorkspaceMembership.workspace_id == workspace_id)
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().unique().all())

    async def get_first_member_verification_status(self, workspace_id: UUID) -> bool:
        """Check whether the first member of a workspace has a verified identity."""
        stmt = (
            select(User.identity_verification_status)
            .join(WorkspaceMembership, User.id == WorkspaceMembership.user_id)
            .where(WorkspaceMembership.workspace_id == workspace_id)
            .limit(1)
        )
        result = await self.session.execute(stmt)
        row = result.first()
        return row[0] == IdentityVerificationStatus.verified if row else False

    # ------------------------------------------------------------------
    # User / membership lookups (impersonation from detail)
    # ------------------------------------------------------------------

    async def get_user_by_id(self, user_id: UUID) -> User | None:
        """Fetch a user by primary key (for admin impersonation)."""
        stmt = select(User).where(User.id == user_id)
        result = await self.session.execute(stmt)
        return result.scalars().one_or_none()

    async def get_membership(
        self, user_id: UUID, workspace_id: UUID
    ) -> WorkspaceMembership | None:
        """Check if a user is a member of a workspace."""
        stmt = select(WorkspaceMembership).where(
            WorkspaceMembership.user_id == user_id,
            WorkspaceMembership.workspace_id == workspace_id,
        )
        result = await self.session.execute(stmt)
        return result.scalars().one_or_none()

    async def append_internal_note(self, workspace: Workspace, note: str) -> Workspace:
        """Append a timestamped note to the workspace's internal notes."""
        timestamp = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")
        full_note = f"[{timestamp}] {note}"
        if workspace.internal_notes:
            workspace.internal_notes = f"{workspace.internal_notes}\n\n{full_note}"
        else:
            workspace.internal_notes = full_note
        return await self.update(workspace, update_dict={})
