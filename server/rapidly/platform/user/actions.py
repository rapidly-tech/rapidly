"""User lifecycle service: signup, identity verification, and account deletion."""

from typing import Any
from uuid import UUID

import stripe as stripe_lib
import structlog

from rapidly.core.anonymization import anonymize_email_for_deletion
from rapidly.errors import RapidlyError
from rapidly.integrations.stripe import actions as stripe_service
from rapidly.logging import Logger
from rapidly.models import User
from rapidly.models.user import IdentityVerificationStatus
from rapidly.platform.workspace.queries import WorkspaceRepository
from rapidly.postgres import AsyncSession
from rapidly.worker import dispatch_task

from .queries import UserRepository
from .types import (
    BlockingWorkspace,
    UserDeletionBlockedReason,
    UserDeletionResponse,
    UserIdentityVerification,
    UserSignupAttribution,
)

_log: Logger = structlog.get_logger(__name__)


# ── Errors ────────────────────────────────────────────────────────────


class UserError(RapidlyError):
    """Base for user-domain business logic errors."""


class IdentityAlreadyVerified(UserError):
    def __init__(self, user_id: UUID) -> None:
        self.user_id = user_id
        super().__init__("Your identity is already verified.", 403)


class IdentityVerificationProcessing(UserError):
    def __init__(self, user_id: UUID) -> None:
        self.user_id = user_id
        super().__init__("Your identity verification is still processing.", 403)


class IdentityVerificationDoesNotExist(UserError):
    def __init__(self, verification_id: str) -> None:
        self.identity_verification_id = verification_id
        super().__init__(
            f"Verification session {verification_id} has no associated user"
        )


class InvalidAccount(UserError):
    def __init__(self, account_id: UUID) -> None:
        self.account_id = account_id
        super().__init__(f"Account {account_id} does not exist or is inaccessible")


# ── Lookup / creation ──


async def get_by_email_or_create(
    session: AsyncSession,
    email: str,
    *,
    signup_attribution: UserSignupAttribution | None = None,
) -> tuple[User, bool]:
    repo = UserRepository.from_session(session)
    existing = await repo.get_by_email(email)
    if existing is not None:
        return existing, False
    return await create_by_email(
        session, email, signup_attribution=signup_attribution
    ), True


async def create_by_email(
    session: AsyncSession,
    email: str,
    signup_attribution: UserSignupAttribution | None = None,
) -> User:
    repo = UserRepository.from_session(session)
    new_user = await repo.create(
        User(email=email, oauth_accounts=[], signup_attribution=signup_attribution),
        flush=True,
    )
    dispatch_task("user.on_after_signup", user_id=new_user.id)
    return new_user


# ── Identity verification (Stripe Identity) ──


async def create_identity_verification(
    session: AsyncSession, user: User
) -> UserIdentityVerification:
    _guard_verification_state(user)

    vs = await _get_or_create_verification_session(user)

    repo = UserRepository.from_session(session)
    await repo.update(user, update_dict={"identity_verification_id": vs.id})

    if vs.client_secret is None:
        raise ValueError("Verification session client_secret must not be None")
    return UserIdentityVerification(id=vs.id, client_secret=vs.client_secret)


def _guard_verification_state(user: User) -> None:
    if user.identity_verified:
        raise IdentityAlreadyVerified(user.id)
    if user.identity_verification_status == IdentityVerificationStatus.pending:
        raise IdentityVerificationProcessing(user.id)


async def _get_or_create_verification_session(
    user: User,
) -> stripe_lib.identity.VerificationSession:
    if user.identity_verification_id is not None:
        existing = await stripe_service.get_verification_session(
            user.identity_verification_id
        )
        if existing is not None and existing.status == "requires_input":
            return existing
    return await stripe_service.create_verification_session(user)


async def _transition_verification(
    session: AsyncSession,
    vs: stripe_lib.identity.VerificationSession,
    target_status: IdentityVerificationStatus,
) -> User:
    """Shared logic for verification state transitions."""
    repo = UserRepository.from_session(session)
    user = await repo.get_by_identity_verification_id(vs.id)
    if user is None:
        raise IdentityVerificationDoesNotExist(vs.id)
    return await repo.update(
        user, update_dict={"identity_verification_status": target_status}
    )


async def identity_verification_verified(
    session: AsyncSession,
    verification_session: stripe_lib.identity.VerificationSession,
) -> User:
    if verification_session.status != "verified":
        raise ValueError(f"Expected verified status, got {verification_session.status}")
    return await _transition_verification(
        session, verification_session, IdentityVerificationStatus.verified
    )


async def identity_verification_pending(
    session: AsyncSession,
    verification_session: stripe_lib.identity.VerificationSession,
) -> User:
    repo = UserRepository.from_session(session)
    user = await repo.get_by_identity_verification_id(verification_session.id)
    if user is None:
        raise IdentityVerificationDoesNotExist(verification_session.id)

    # Already verified — a late webhook shouldn't regress status.
    if user.identity_verified:
        return user

    if verification_session.status != "processing":
        raise ValueError(
            f"Expected processing status, got {verification_session.status}"
        )
    return await repo.update(
        user,
        update_dict={
            "identity_verification_status": IdentityVerificationStatus.pending
        },
    )


async def identity_verification_failed(
    session: AsyncSession,
    verification_session: stripe_lib.identity.VerificationSession,
) -> User:
    return await _transition_verification(
        session, verification_session, IdentityVerificationStatus.failed
    )


async def delete_identity_verification(session: AsyncSession, user: User) -> User:
    """Delete identity verification for a user.

    Resets the user's identity verification status to unverified and
    redacts the verification session in Stripe.
    """
    repository = UserRepository.from_session(session)

    if user.identity_verification_id is not None:
        try:
            await stripe_service.redact_verification_session(
                user.identity_verification_id
            )
        except stripe_lib.InvalidRequestError as e:
            _log.warning(
                "stripe.identity.verification_session.redact.not_found",
                identity_verification_id=user.identity_verification_id,
                error=str(e),
            )

    return await repository.update(
        user,
        update_dict={
            "identity_verification_status": IdentityVerificationStatus.unverified,
            "identity_verification_id": None,
        },
    )


# ── Account deletion (GDPR) ──


async def check_can_delete(
    session: AsyncSession,
    user: User,
) -> UserDeletionResponse:
    """Return deletion blockers. Empty list means user is safe to delete."""
    org_repo = WorkspaceRepository.from_session(session)
    active_orgs = await org_repo.get_all_by_user(user.id)

    blockers = [
        BlockingWorkspace(id=o.id, slug=o.slug, name=o.name) for o in active_orgs
    ]
    reasons = [UserDeletionBlockedReason.HAS_ACTIVE_WORKSPACES] if blockers else []

    return UserDeletionResponse(
        deleted=False,
        blocked_reasons=reasons,
        blocking_workspaces=blockers,
    )


async def request_deletion(
    session: AsyncSession,
    user: User,
) -> UserDeletionResponse:
    """Request deletion of the user account.

    Flow:
    1. Check if user has any active workspaces -> block if yes
    2. Soft delete the user

    Note: The user's Account (payout account) is not deleted here.
    Accounts are tied to workspaces and should be deleted when the
    workspace is deleted, not when the user account is deleted.
    """
    check_result = await check_can_delete(session, user)

    if check_result.blocked_reasons:
        return check_result

    # Soft delete the user
    await soft_delete_user(session, user)

    return UserDeletionResponse(
        deleted=True,
        blocked_reasons=[],
        blocking_workspaces=[],
    )


async def soft_delete_user(
    session: AsyncSession,
    user: User,
) -> User:
    """Anonymise PII, purge linked records, and soft-delete the user."""
    repo = UserRepository.from_session(session)

    pii_updates: dict[str, Any] = {
        "email": anonymize_email_for_deletion(user.email),
    }
    if user.avatar_url:
        pii_updates["avatar_url"] = None
    if user.meta:
        pii_updates["meta"] = {}

    await _purge_linked_records(session, user)

    user = await repo.update(user, update_dict=pii_updates)
    await repo.soft_delete(user)
    _log.info("user.deleted", user_id=user.id)
    return user


async def _purge_linked_records(session: AsyncSession, user: User) -> None:
    """Hard-delete OAuth accounts and soft-delete notification recipients."""
    repo = UserRepository.from_session(session)
    await repo.delete_oauth_accounts(user.id)
    await repo.soft_delete_notification_recipients(user.id)
    _log.info("user.linked_records_purged", user_id=user.id)
