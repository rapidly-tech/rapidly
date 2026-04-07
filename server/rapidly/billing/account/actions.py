"""Stripe Connect account lifecycle: creation, onboarding, and admin management."""

from __future__ import annotations

import uuid
from collections.abc import Sequence

import stripe as stripe_lib
import structlog
from sqlalchemy.orm.strategy_options import joinedload

from rapidly.billing.account.queries import AccountRepository
from rapidly.core.pagination import PaginationParams
from rapidly.enums import AccountType
from rapidly.errors import RapidlyError
from rapidly.identity.auth.models import AuthPrincipal
from rapidly.integrations.stripe import actions as stripe
from rapidly.models import Account, User, Workspace
from rapidly.models.user import IdentityVerificationStatus
from rapidly.platform.user.queries import UserRepository
from rapidly.postgres import AsyncReadSession, AsyncSession

from .types import (
    AccountCreateForWorkspace,
    AccountLink,
    AccountUpdate,
)

_log = structlog.get_logger(__name__)

# Eager-loaded relationships used whenever an Account is fetched.
_ACCOUNT_EAGER_LOADS = (joinedload(Account.users), joinedload(Account.workspaces))


class AccountServiceError(RapidlyError):
    """Base error for account-related business logic failures."""


class AccountExternalIdDoesNotExist(AccountServiceError):
    def __init__(self, external_id: str) -> None:
        self.external_id = external_id
        super().__init__(f"No account with external ID {external_id}")


class CannotChangeAdminError(AccountServiceError):
    def __init__(self, reason: str) -> None:
        super().__init__(f"Cannot change account admin: {reason}")


class UserNotWorkspaceMemberError(AccountServiceError):
    def __init__(self, user_id: uuid.UUID, workspace_id: uuid.UUID) -> None:
        super().__init__(f"User {user_id} is not a member of workspace {workspace_id}")


# ── Reads ──


async def search(
    session: AsyncReadSession,
    auth_subject: AuthPrincipal[User],
    *,
    pagination: PaginationParams,
) -> tuple[Sequence[Account], int]:
    repo = AccountRepository.from_session(session)
    stmt = repo.get_readable_statement(auth_subject).options(*_ACCOUNT_EAGER_LOADS)
    return await repo.paginate(stmt, limit=pagination.limit, page=pagination.page)


async def get(
    session: AsyncReadSession,
    auth_subject: AuthPrincipal[User | Workspace],
    id: uuid.UUID,
) -> Account | None:
    repo = AccountRepository.from_session(session)
    stmt = (
        repo.get_readable_statement(auth_subject)
        .where(Account.id == id)
        .options(*_ACCOUNT_EAGER_LOADS)
    )
    return await repo.get_one_or_none(stmt)


async def _get_unrestricted(
    session: AsyncReadSession,
    id: uuid.UUID,
) -> Account | None:
    repo = AccountRepository.from_session(session)
    stmt = (
        repo.get_base_statement().where(Account.id == id).options(*_ACCOUNT_EAGER_LOADS)
    )
    return await repo.get_one_or_none(stmt)


async def is_user_admin(
    session: AsyncReadSession, account_id: uuid.UUID, user: User
) -> bool:
    account = await _get_unrestricted(session, account_id)
    if account is None:
        return False
    return account.admin_id == user.id


# ── Writes ──


async def update(
    session: AsyncSession, account: Account, account_update: AccountUpdate
) -> Account:
    repo = AccountRepository.from_session(session)
    return await repo.update(
        account, update_dict=account_update.model_dump(exclude_unset=True)
    )


async def delete(session: AsyncSession, account: Account) -> Account:
    repo = AccountRepository.from_session(session)
    return await repo.soft_delete(account)


async def delete_stripe_account(session: AsyncSession, account: Account) -> None:
    """Remove the Stripe account and reset associated DB columns."""
    if not account.stripe_id:
        raise AccountServiceError("Account does not have a Stripe ID")

    # Confirm the account is still present on Stripe before removing it
    if not await stripe.account_exists(account.stripe_id):
        raise AccountServiceError(
            f"Stripe Account ID {account.stripe_id} doesn't exist"
        )

    # Issue the deletion request to Stripe
    await stripe.delete_account(account.stripe_id)

    # Wipe Stripe-specific fields from the local record
    repo = AccountRepository.from_session(session)
    await repo.clear_stripe_fields(account)


async def disconnect_stripe(session: AsyncSession, account: Account) -> Account:
    if not account.stripe_id:
        raise AccountServiceError("Account does not have a Stripe ID")

    repo = AccountRepository.from_session(session)
    old_stripe_id = account.stripe_id

    archive_account = Account(
        status=account.status,
        admin_id=account.admin_id,
        account_type=account.account_type,
        stripe_id=old_stripe_id,
        email=account.email,
        country=account.country,
        currency=account.currency,
        is_details_submitted=account.is_details_submitted,
        is_charges_enabled=account.is_charges_enabled,
        is_payouts_enabled=account.is_payouts_enabled,
        business_type=account.business_type,
        data=account.data,
        processor_fees_applicable=account.processor_fees_applicable,
        _platform_fee_percent=account._platform_fee_percent,
        _platform_fee_fixed=account._platform_fee_fixed,
        next_review_threshold=account.next_review_threshold,
        campaign_id=account.campaign_id,
    )
    archive_account.set_deleted_at()
    await repo.create(archive_account, flush=True)

    await repo.clear_stripe_id(account)

    return archive_account


async def create_account(
    session: AsyncSession,
    *,
    admin: User,
    account_create: AccountCreateForWorkspace,
) -> Account:
    if account_create.account_type != AccountType.stripe:
        raise ValueError(f"Unsupported account type: {account_create.account_type}")
    account = await _create_stripe_account(session, admin, account_create)
    return account


async def get_or_create_account_for_workspace(
    session: AsyncSession,
    workspace: Workspace,
    admin: User,
    account_create: AccountCreateForWorkspace,
    *,
    force_new: bool = False,
) -> Account:
    """Return the workspace's current account, or provision a fresh one.

    When the workspace already owns an account whose stripe_id was
    cleared (i.e. previously disconnected), a replacement Stripe account
    is created.  If no account exists at all, one is created and linked
    to the workspace.

    When ``force_new`` is True, the existing account is disconnected and
    a brand new Stripe account is provisioned.
    """

    # See whether the workspace is already associated with an account
    if workspace.account_id:
        repository = AccountRepository.from_session(session)
        account = await repository.get_by_id(
            workspace.account_id,
            options=(
                joinedload(Account.users),
                joinedload(Account.workspaces),
            ),
        )

        # Force new: skip the existing account and fall through to create a
        # brand-new one.  The old account is NOT deleted — it stays visible in
        # the accounts list so the user can switch back to it later.
        if account and force_new:
            account = None  # Fall through to provision a new one below

        elif account and not account.stripe_id:
            if account_create.account_type != AccountType.stripe:
                raise ValueError(
                    f"Unsupported account type: {account_create.account_type}"
                )
            try:
                stripe_account = await stripe.create_account(account_create, name=None)
            except stripe_lib.StripeError as e:
                if e.user_message:
                    raise AccountServiceError(e.user_message) from e
                else:
                    raise AccountServiceError(
                        "An unexpected Stripe error happened"
                    ) from e

            # Populate the account row with the fresh Stripe data
            if stripe_account.default_currency is None:
                raise ValueError("Stripe account is missing a default currency")
            await repository.update_stripe_data(
                account,
                stripe_id=stripe_account.id,
                email=stripe_account.email,
                country=stripe_account.country,
                currency=stripe_account.default_currency,
                is_details_submitted=stripe_account.details_submitted or False,
                is_charges_enabled=stripe_account.charges_enabled or False,
                is_payouts_enabled=stripe_account.payouts_enabled or False,
                business_type=stripe_account.business_type,
                data=stripe_account.to_dict(),
            )

            return account
        elif account:
            return account

    # Workspace has no account yet — provision one
    account = await create_account(session, admin=admin, account_create=account_create)

    # Attach the new account to the workspace (late import breaks circular ref)
    from rapidly.platform.workspace import actions as workspace_service

    await workspace_service.set_account(
        session,
        auth_subject=AuthPrincipal(subject=admin, scopes=set(), session=None),
        workspace=workspace,
        account_id=account.id,
        skip_pending_check=force_new,
    )

    repo = AccountRepository.from_session(session)
    await repo.refresh_relations(account)

    return account


async def _build_stripe_account_name(
    session: AsyncSession, account: Account
) -> str | None:
    """Build a human-readable name for the Stripe Express dashboard."""
    repo = AccountRepository.from_session(session)
    await repo.refresh_relations(account)
    parts = [f"user/{u.email}" for u in account.users]
    parts.extend(f"org/{o.slug}" for o in account.workspaces)
    return "\u00b7".join(parts)  # middle-dot separator


async def _create_stripe_account(
    session: AsyncSession,
    admin: User,
    account_create: AccountCreateForWorkspace,
) -> Account:
    try:
        stripe_account = await stripe.create_account(account_create, name=None)
    except stripe_lib.StripeError as e:
        if e.user_message:
            raise AccountServiceError(e.user_message) from e
        else:
            raise AccountServiceError("An unexpected Stripe error happened") from e

    account = Account(
        status=Account.Status.ONBOARDING_STARTED,
        admin_id=admin.id,
        account_type=account_create.account_type,
        stripe_id=stripe_account.id,
        email=stripe_account.email,
        country=stripe_account.country,
        currency=stripe_account.default_currency,
        is_details_submitted=stripe_account.details_submitted,
        is_charges_enabled=stripe_account.charges_enabled,
        is_payouts_enabled=stripe_account.payouts_enabled,
        business_type=stripe_account.business_type,
        data=stripe_account.to_dict(),
        users=[],
        workspaces=[],
    )

    repo = AccountRepository.from_session(session)
    await repo.create(account, flush=True)

    return account


async def update_account_from_stripe(
    session: AsyncSession, *, stripe_account: stripe_lib.Account
) -> Account:
    repository = AccountRepository.from_session(session)
    account = await repository.get_by_stripe_id(stripe_account.id)
    if account is None:
        raise AccountExternalIdDoesNotExist(stripe_account.id)

    if stripe_account.default_currency is None:
        raise ValueError("Stripe account is missing a default currency")
    await repository.update_stripe_data(
        account,
        email=stripe_account.email,
        country=stripe_account.country,
        currency=stripe_account.default_currency,
        is_details_submitted=stripe_account.details_submitted or False,
        is_charges_enabled=stripe_account.charges_enabled or False,
        is_payouts_enabled=stripe_account.payouts_enabled or False,
        data=stripe_account.to_dict(),
    )

    # Reflect Stripe capability changes in the workspace's own status
    # Late import to sidestep circular module dependency
    from rapidly.platform.workspace import actions as workspace_service

    await workspace_service.update_status_from_stripe_account(session, account)

    return account


# ── Onboarding ──


async def onboarding_link(account: Account, return_path: str) -> AccountLink | None:
    if account.account_type == AccountType.stripe:
        if account.stripe_id is None:
            raise ValueError("account.stripe_id must not be None for Stripe accounts")
        account_link = await stripe.create_account_link(account.stripe_id, return_path)
        return AccountLink(url=account_link.url)

    return None


async def dashboard_link(account: Account) -> AccountLink | None:
    if account.account_type == AccountType.stripe:
        if account.stripe_id is None:
            raise ValueError("account.stripe_id must not be None for Stripe accounts")
        account_link = await stripe.create_login_link(account.stripe_id)
        return AccountLink(url=account_link.url)

    return None


# ── Stripe sync ──


async def sync_to_upstream(session: AsyncSession, account: Account) -> None:
    if account.account_type != AccountType.stripe:
        return

    if not account.stripe_id:
        return

    name = await _build_stripe_account_name(session, account)
    await stripe.update_account(account.stripe_id, name)


async def sync_from_stripe(session: AsyncSession, account: Account) -> None:
    """Refresh account flags from Stripe (details_submitted, charges/payouts enabled)."""
    if not account.stripe_id:
        return
    try:
        stripe_account = await stripe_lib.Account.retrieve_async(account.stripe_id)
        repo = AccountRepository.from_session(session)
        await repo.update_stripe_data(
            account,
            is_details_submitted=stripe_account.details_submitted or False,
            is_charges_enabled=stripe_account.charges_enabled or False,
            is_payouts_enabled=stripe_account.payouts_enabled or False,
        )
    except (stripe_lib.StripeError, ConnectionError):
        _log.debug(
            "Non-critical Stripe sync failed, will update on next webhook",
            account_id=str(account.id),
            stripe_id=account.stripe_id,
        )


# ── Admin transfer ──


async def change_admin(
    session: AsyncSession,
    account: Account,
    new_admin_id: uuid.UUID,
    workspace_id: uuid.UUID,
) -> Account:
    _guard_admin_change(account, new_admin_id)

    user_repo = UserRepository.from_session(session)
    if not await user_repo.is_workspace_member(new_admin_id, workspace_id):
        raise UserNotWorkspaceMemberError(new_admin_id, workspace_id)

    new_admin = await user_repo.get_by_id(new_admin_id)
    if new_admin is None:
        raise UserNotWorkspaceMemberError(new_admin_id, workspace_id)

    if new_admin.identity_verification_status != IdentityVerificationStatus.verified:
        raise CannotChangeAdminError(
            f"New admin must be verified. "
            f"Current status: {new_admin.identity_verification_status.display_name}"
        )

    repo = AccountRepository.from_session(session)
    return await repo.update(account, update_dict={"admin_id": new_admin_id})


def _guard_admin_change(account: Account, new_admin_id: uuid.UUID) -> None:
    """Pre-condition checks before an admin transfer."""
    if account.stripe_id:
        raise CannotChangeAdminError(
            "Stripe account must be deleted before changing admin"
        )
    if account.admin_id == new_admin_id:
        raise CannotChangeAdminError("New admin is the same as current admin")
