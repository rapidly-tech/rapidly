"""User database queries: email, OAuth, Stripe, and workspace membership lookups.

``UserRepository`` supports case-insensitive email search, OAuth
platform-account correlation, Stripe customer ID resolution, and
workspace membership checks with soft-delete and blocked-user filtering.
"""

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import delete, func, select, update

from rapidly.core.queries import (
    Repository,
    SoftDeleteByIdMixin,
    SoftDeleteMixin,
    SortableMixin,
)
from rapidly.core.queries.base import SortingClause
from rapidly.models import (
    NotificationRecipient,
    OAuthAccount,
    User,
    WorkspaceMembership,
)
from rapidly.models.user import OAuthPlatform

from .ordering import UserSortProperty


class OAuthAccountRepository(Repository[OAuthAccount]):
    """OAuth account lookups and management."""

    model = OAuthAccount

    async def get_by_platform_and_account_id(
        self, platform: OAuthPlatform, account_id: str
    ) -> OAuthAccount | None:
        stmt = self.get_base_statement().where(
            OAuthAccount.platform == platform,
            OAuthAccount.account_id == account_id,
        )
        return await self.get_one_or_none(stmt)

    async def get_all_by_user_and_platform(
        self, user_id: UUID, platform: OAuthPlatform
    ) -> list[OAuthAccount]:
        stmt = self.get_base_statement().where(
            OAuthAccount.platform == platform,
            OAuthAccount.user_id == user_id,
        )
        return list(await self.get_all(stmt))

    async def count_by_user_excluding(
        self, user_id: UUID, *, exclude_ids: list[UUID]
    ) -> int:
        stmt = select(func.count(OAuthAccount.id)).where(
            OAuthAccount.user_id == user_id,
            OAuthAccount.id.not_in(exclude_ids),
        )
        result = await self.session.execute(stmt)
        return result.scalar_one()


class UserRepository(
    SortableMixin[User, UserSortProperty],
    SoftDeleteByIdMixin[User, UUID],
    SoftDeleteMixin[User],
    Repository[User],
):
    """User lookups with soft-delete awareness and sort support."""

    model = User

    # ------------------------------------------------------------------
    # Sorting
    # ------------------------------------------------------------------

    def get_sorting_clause(self, property: UserSortProperty) -> SortingClause:
        match property:
            case UserSortProperty.created_at:
                return self.model.created_at
            case UserSortProperty.email:
                return self.model.email

    # ------------------------------------------------------------------
    # Email & Stripe lookups
    # ------------------------------------------------------------------

    async def get_by_email(
        self,
        email: str,
        *,
        include_deleted: bool = False,
        included_blocked: bool = False,
    ) -> User | None:
        stmt = self.get_base_statement(include_deleted=include_deleted).where(
            func.lower(User.email) == email.lower()
        )
        if not included_blocked:
            stmt = stmt.where(User.blocked_at.is_(None))
        return await self.get_one_or_none(stmt)

    async def get_by_stripe_customer_id(
        self,
        stripe_customer_id: str,
        *,
        include_deleted: bool = False,
        included_blocked: bool = False,
    ) -> User | None:
        stmt = self.get_base_statement(include_deleted=include_deleted).where(
            User.stripe_customer_id == stripe_customer_id
        )
        if not included_blocked:
            stmt = stmt.where(User.blocked_at.is_(None))
        return await self.get_one_or_none(stmt)

    # ------------------------------------------------------------------
    # OAuth lookups
    # ------------------------------------------------------------------

    async def get_by_oauth_account(
        self,
        platform: OAuthPlatform,
        account_id: str,
        *,
        include_deleted: bool = False,
        included_blocked: bool = False,
    ) -> User | None:
        stmt = (
            self.get_base_statement(include_deleted=include_deleted)
            .join(User.oauth_accounts)
            .where(
                OAuthAccount.platform == platform,
                OAuthAccount.account_id == account_id,
            )
        )
        if not included_blocked:
            stmt = stmt.where(User.blocked_at.is_(None))
        return await self.get_one_or_none(stmt)

    # ------------------------------------------------------------------
    # Identity verification
    # ------------------------------------------------------------------

    async def get_by_identity_verification_id(
        self,
        identity_verification_id: str,
        *,
        include_deleted: bool = False,
        included_blocked: bool = False,
    ) -> User | None:
        stmt = self.get_base_statement(include_deleted=include_deleted).where(
            User.identity_verification_id == identity_verification_id
        )
        if not included_blocked:
            stmt = stmt.where(User.blocked_at.is_(None))
        return await self.get_one_or_none(stmt)

    # ------------------------------------------------------------------
    # Workspace membership
    # ------------------------------------------------------------------

    async def get_all_by_workspace(
        self,
        workspace_id: UUID,
        *,
        include_deleted: bool = False,
        included_blocked: bool = False,
    ) -> Sequence[User]:
        stmt = (
            self.get_base_statement(include_deleted=include_deleted)
            .join(WorkspaceMembership, WorkspaceMembership.user_id == User.id)
            .where(
                WorkspaceMembership.deleted_at.is_(None),
                WorkspaceMembership.workspace_id == workspace_id,
            )
        )
        if not included_blocked:
            stmt = stmt.where(User.blocked_at.is_(None))
        return await self.get_all(stmt)

    async def is_workspace_member(
        self,
        user_id: UUID,
        workspace_id: UUID,
    ) -> bool:
        stmt = select(WorkspaceMembership).where(
            WorkspaceMembership.user_id == user_id,
            WorkspaceMembership.workspace_id == workspace_id,
            WorkspaceMembership.deleted_at.is_(None),
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none() is not None

    # ------------------------------------------------------------------
    # Deletion helpers
    # ------------------------------------------------------------------

    async def delete_oauth_accounts(self, user_id: UUID) -> None:
        """Hard-delete all OAuth accounts for a user."""
        await self.session.execute(
            delete(OAuthAccount).where(OAuthAccount.user_id == user_id)
        )

    async def soft_delete_notification_recipients(self, user_id: UUID) -> None:
        """Soft-delete all active notification recipients for a user."""
        await self.session.execute(
            update(NotificationRecipient)
            .where(
                NotificationRecipient.user_id == user_id,
                NotificationRecipient.deleted_at.is_(None),
            )
            .values(deleted_at=func.now())
        )
