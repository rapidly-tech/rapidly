"""Payout account persistence: Stripe lookup, owner/org resolution, and ACL filtering."""

import uuid
from uuid import UUID

from sqlalchemy import Select, false

from rapidly.core.queries import (
    Options,
    Repository,
    SoftDeleteByIdMixin,
    SoftDeleteMixin,
)
from rapidly.identity.auth.models import (
    AuthPrincipal,
    User,
    is_user_principal,
    is_workspace_principal,
)
from rapidly.models import Account, Workspace


class AccountRepository(
    SoftDeleteByIdMixin[Account, UUID],
    SoftDeleteMixin[Account],
    Repository[Account],
):
    """Queries for payout accounts with Stripe, user, and workspace joins."""

    model = Account

    # ── Stripe lookup ─────────────────────────────────────────────────

    async def get_by_stripe_id(
        self,
        stripe_id: str,
        *,
        options: Options = (),
        include_deleted: bool = False,
    ) -> Account | None:
        stmt = (
            self.get_base_statement(include_deleted=include_deleted)
            .where(Account.stripe_id == stripe_id)
            .options(*options)
        )
        return await self.get_one_or_none(stmt)

    # ── Owner resolution ──────────────────────────────────────────────

    async def get_by_user(
        self,
        user_id: uuid.UUID,
        *,
        options: Options = (),
        include_deleted: bool = False,
    ) -> Account | None:
        """Find the account where *user_id* is the linked admin user."""
        stmt = (
            self.get_base_statement(include_deleted=include_deleted)
            .join(User, onclause=User.account_id == Account.id)
            .where(User.id == user_id)
            .options(*options)
        )
        return await self.get_one_or_none(stmt)

    async def get_by_workspace(
        self,
        workspace_id: uuid.UUID,
        *,
        options: Options = (),
        include_deleted: bool = False,
    ) -> Account | None:
        """Find the account linked to *workspace_id*."""
        stmt = (
            self.get_base_statement(include_deleted=include_deleted)
            .join(Workspace, onclause=Workspace.account_id == Account.id)
            .where(Workspace.id == workspace_id)
            .options(*options)
        )
        return await self.get_one_or_none(stmt)

    # ── Stripe field management ────────────────────────────────────────

    async def clear_stripe_fields(self, account: Account) -> Account:
        """Reset all Stripe-specific columns on the account."""
        return await self.update(
            account,
            update_dict={
                "stripe_id": None,
                "is_details_submitted": False,
                "is_charges_enabled": False,
                "is_payouts_enabled": False,
            },
        )

    async def clear_stripe_id(self, account: Account) -> Account:
        """Remove only the stripe_id from the account."""
        return await self.update(account, update_dict={"stripe_id": None})

    async def update_stripe_data(
        self,
        account: Account,
        *,
        stripe_id: str | None = None,
        email: str | None = None,
        country: str | None = None,
        currency: str | None = None,
        is_details_submitted: bool | None = None,
        is_charges_enabled: bool | None = None,
        is_payouts_enabled: bool | None = None,
        business_type: str | None = None,
        data: dict[str, object] | None = None,
    ) -> Account:
        """Update the account with Stripe-sourced field values."""
        update_dict: dict[str, object] = {}
        if stripe_id is not None:
            update_dict["stripe_id"] = stripe_id
        if email is not None:
            update_dict["email"] = email
        if country is not None:
            update_dict["country"] = country
        if currency is not None:
            update_dict["currency"] = currency
        if is_details_submitted is not None:
            update_dict["is_details_submitted"] = is_details_submitted
        if is_charges_enabled is not None:
            update_dict["is_charges_enabled"] = is_charges_enabled
        if is_payouts_enabled is not None:
            update_dict["is_payouts_enabled"] = is_payouts_enabled
        if business_type is not None:
            update_dict["business_type"] = business_type
        if data is not None:
            update_dict["data"] = data
        return await self.update(account, update_dict=update_dict)

    async def refresh_relations(self, account: Account) -> None:
        """Refresh the users and workspaces relationships on the account."""
        await self.session.refresh(account, {"users", "workspaces"})

    # ── ACL filtering ─────────────────────────────────────────────────

    def get_readable_statement(
        self, auth_subject: AuthPrincipal[User | Workspace]
    ) -> Select[tuple[Account]]:
        """Return a statement scoped to what *auth_subject* may see."""
        stmt = self.get_base_statement()

        if is_user_principal(auth_subject):
            stmt = stmt.where(Account.admin_id == auth_subject.subject.id)
        elif is_workspace_principal(auth_subject):
            # Workspace tokens cannot enumerate accounts
            stmt = stmt.where(false())

        return stmt
