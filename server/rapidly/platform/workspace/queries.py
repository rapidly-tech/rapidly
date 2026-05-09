"""Workspace persistence layer with review status tracking.

``WorkspaceRepository`` handles slug / ID look-ups, member-scoped
listing, status transitions, and account linking.
``WorkspaceReviewRepository`` manages the one-to-one review record
that accompanies each workspace through the onboarding pipeline.
"""

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import Select, func, or_, select, update

from rapidly.core.queries import (
    Repository,
    SoftDeleteByIdMixin,
    SoftDeleteMixin,
    SortableMixin,
    SortingClause,
)
from rapidly.core.queries.base import Options
from rapidly.identity.auth.models import (
    AuthPrincipal,
    is_user_principal,
    is_workspace_principal,
)
from rapidly.models import Account, Customer, User, Workspace, WorkspaceMembership
from rapidly.models.workspace import WorkspaceStatus
from rapidly.models.workspace_review import WorkspaceReview
from rapidly.postgres import AsyncReadSession

from .ordering import WorkspaceSortProperty


class WorkspaceRepository(
    SortableMixin[Workspace, WorkspaceSortProperty],
    SoftDeleteByIdMixin[Workspace, UUID],
    SoftDeleteMixin[Workspace],
    Repository[Workspace],
):
    """Workspace queries with slug lookup, feature-flag filtering, and invoice numbering."""

    model = Workspace

    # ── Reads ──

    async def get_by_id(
        self,
        id: UUID,
        *,
        options: Options = (),
        include_deleted: bool = False,
        include_blocked: bool = False,
    ) -> Workspace | None:
        statement = (
            self.get_base_statement(include_deleted=include_deleted)
            .where(self.model.id == id)
            .options(*options)
        )

        if not include_blocked:
            statement = statement.where(self.model.blocked_at.is_(None))

        return await self.get_one_or_none(statement)

    async def get_accessible_by_id(
        self,
        id: UUID,
        user_id: UUID,
    ) -> Workspace | None:
        """Fetch a workspace by ID that is accessible to the given user."""
        statement = self.get_base_statement().where(
            Workspace.id == id,
            Workspace.id.in_(
                select(WorkspaceMembership.workspace_id).where(
                    WorkspaceMembership.user_id == user_id,
                    WorkspaceMembership.deleted_at.is_(None),
                )
            ),
        )
        return await self.get_one_or_none(statement)

    async def get_by_id_with_account(
        self,
        id: UUID,
        *,
        include_deleted: bool = False,
        include_blocked: bool = True,
    ) -> Workspace | None:
        from sqlalchemy.orm import joinedload

        statement = (
            self.get_base_statement(include_deleted=include_deleted)
            .options(joinedload(Workspace.account))
            .where(self.model.id == id)
        )

        if not include_blocked:
            statement = statement.where(self.model.blocked_at.is_(None))

        return await self.get_one_or_none(statement)

    # ── Slug management ──

    async def get_by_slug(self, slug: str) -> Workspace | None:
        statement = self.get_base_statement().where(Workspace.slug == slug)
        return await self.get_one_or_none(statement)

    async def slug_exists(self, slug: str) -> bool:
        """Check if slug exists, including soft-deleted workspaces.

        Soft-deleted workspaces are included to prevent slug reuse,
        ensuring admin links continue to work.
        """
        statement = self.get_base_statement(include_deleted=True).where(
            Workspace.slug == slug
        )
        result = await self.get_one_or_none(statement)
        return result is not None

    async def get_by_customer(self, customer_id: UUID) -> Workspace:
        statement = (
            self.get_base_statement()
            .join(Customer, Customer.workspace_id == Workspace.id)
            .where(Customer.id == customer_id)
        )
        return await self.get_one(statement)

    async def get_all_by_user(self, user: UUID) -> Sequence[Workspace]:
        statement = (
            self.get_base_statement()
            .join(WorkspaceMembership)
            .where(
                WorkspaceMembership.user_id == user,
                WorkspaceMembership.deleted_at.is_(None),
                Workspace.blocked_at.is_(None),
            )
        )
        return await self.get_all(statement)

    async def get_all_by_account(
        self, account: UUID, *, options: Options = ()
    ) -> Sequence[Workspace]:
        statement = (
            self.get_base_statement()
            .where(
                Workspace.account_id == account,
                Workspace.blocked_at.is_(None),
            )
            .options(*options)
        )
        return await self.get_all(statement)

    def get_sorting_clause(self, property: WorkspaceSortProperty) -> SortingClause:
        match property:
            case WorkspaceSortProperty.created_at:
                return self.model.created_at
            case WorkspaceSortProperty.slug:
                return self.model.slug
            case WorkspaceSortProperty.workspace_name:
                return self.model.name
            case WorkspaceSortProperty.next_review_threshold:
                return self.model.next_review_threshold
            case WorkspaceSortProperty.days_in_status:
                # Calculate days since status was last updated
                return (
                    func.extract(
                        "epoch",
                        func.now()
                        - func.coalesce(
                            self.model.status_updated_at, self.model.modified_at
                        ),
                    )
                    / 86400
                )

    def get_readable_statement(
        self, auth_subject: AuthPrincipal[User | Workspace]
    ) -> Select[tuple[Workspace]]:
        statement = self.get_base_statement().where(Workspace.blocked_at.is_(None))

        if is_user_principal(auth_subject):
            user = auth_subject.subject
            statement = statement.where(
                Workspace.id.in_(
                    select(WorkspaceMembership.workspace_id).where(
                        WorkspaceMembership.user_id == user.id,
                        WorkspaceMembership.deleted_at.is_(None),
                    )
                )
            )
        elif is_workspace_principal(auth_subject):
            statement = statement.where(
                Workspace.id == auth_subject.subject.id,
            )

        return statement

    async def get_admin_user(
        self, session: AsyncReadSession, workspace: Workspace
    ) -> User | None:
        """Get the admin user of the workspace from the associated account."""
        if not workspace.account_id:
            return None

        statement = (
            select(User)
            .join(Account, Account.admin_id == User.id)
            .where(
                Account.id == workspace.account_id,
                User.deleted_at.is_(None),
            )
        )
        result = await session.execute(statement)
        return result.unique().scalar_one_or_none()

    async def enable_revops(self, workspace_ids: set[UUID]) -> None:
        statement = self.get_base_statement().where(
            Workspace.id.in_(workspace_ids),
            or_(
                Workspace.feature_settings["revops_enabled"].is_(None),
                Workspace.feature_settings["revops_enabled"].as_boolean().is_(False),
            ),
        )
        orgs = await self.get_all(statement)
        for org in orgs:
            org.feature_settings = {**org.feature_settings, "revops_enabled": True}
            self.session.add(org)
        await self.session.flush()

    # ── Membership ──

    async def reactivate_membership(self, user_id: UUID, workspace_id: UUID) -> None:
        """Un-delete a membership that already exists (IntegrityError path)."""
        stmt = (
            update(WorkspaceMembership)
            .where(
                WorkspaceMembership.user_id == user_id,
                WorkspaceMembership.workspace_id == workspace_id,
            )
            .values(deleted_at=None)
        )
        await self.session.execute(stmt)
        await self.session.flush()

    # ── Account status sync ──

    async def sync_account_status(self, workspace: Workspace) -> None:
        """Sync workspace status to the related account."""
        if not workspace.account_id:
            return

        status_mapping = {
            WorkspaceStatus.ONBOARDING_STARTED: Account.Status.ONBOARDING_STARTED,
            WorkspaceStatus.ACTIVE: Account.Status.ACTIVE,
            WorkspaceStatus.INITIAL_REVIEW: Account.Status.UNDER_REVIEW,
            WorkspaceStatus.ONGOING_REVIEW: Account.Status.UNDER_REVIEW,
            WorkspaceStatus.DENIED: Account.Status.DENIED,
        }

        if workspace.status in status_mapping:
            account_status = status_mapping[workspace.status]
            await self.session.execute(
                update(Account)
                .where(Account.id == workspace.account_id)
                .values(status=account_status)
            )


class WorkspaceReviewRepository(Repository[WorkspaceReview]):
    """Admin review records tied to workspace onboarding verdicts."""

    model = WorkspaceReview

    # ── Reads ──

    async def get_by_workspace(self, workspace_id: UUID) -> WorkspaceReview | None:
        statement = self.get_base_statement().where(
            WorkspaceReview.workspace_id == workspace_id,
            WorkspaceReview.deleted_at.is_(None),
        )
        return await self.get_one_or_none(statement)
