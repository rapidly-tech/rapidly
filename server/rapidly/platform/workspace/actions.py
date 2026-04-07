"""Workspace lifecycle: creation, onboarding, review, payment status, and deletion."""

import builtins
import uuid
from collections.abc import Sequence
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

import structlog
from pydantic import BaseModel, Field
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import joinedload

from rapidly.billing.account import actions as account_service
from rapidly.billing.account.queries import AccountRepository
from rapidly.config import Environment, settings
from rapidly.core.anonymization import (
    anonymize_email_for_deletion,
    anonymize_for_deletion,
)
from rapidly.core.ordering import Sorting
from rapidly.core.pagination import PaginationParams
from rapidly.core.queries import Options
from rapidly.errors import (
    NotPermitted,
    RapidlyError,
    RequestValidationError,
    validation_error,
)
from rapidly.identity.auth.models import AuthPrincipal
from rapidly.messaging.email.react import render_email_template
from rapidly.messaging.email.sender import enqueue_email
from rapidly.messaging.email.types import WorkspaceInviteEmail, WorkspaceInviteProps
from rapidly.messaging.webhook import actions as webhook_service
from rapidly.models import (
    Account,
    User,
    Workspace,
    WorkspaceMembership,
)
from rapidly.models.user import IdentityVerificationStatus
from rapidly.models.webhook_endpoint import WebhookEventType
from rapidly.models.workspace import WorkspaceStatus
from rapidly.models.workspace_review import WorkspaceReview
from rapidly.platform.workspace.ai_validation import validator as workspace_validator
from rapidly.platform.workspace_membership.queries import WorkspaceMembershipRepository
from rapidly.postgres import AsyncReadSession, AsyncSession
from rapidly.posthog import posthog
from rapidly.worker import dispatch_task

from .ordering import WorkspaceSortProperty
from .queries import WorkspaceRepository, WorkspaceReviewRepository
from .types import (
    WorkspaceCreate,
    WorkspaceDeletionBlockedReason,
    WorkspaceUpdate,
)

_log = structlog.get_logger(__name__)

# Workspaces created before this date are grandfathered into the legacy payment flow.
_GRANDFATHERING_CUTOFF = datetime(2025, 8, 4, 9, 0, tzinfo=UTC)


# ── Payment status models ──


class PaymentStepID(StrEnum):
    """Named stages in the payment-account onboarding flow."""

    CREATE_PRODUCT = "create_product"
    INTEGRATE_API = "integrate_api"
    SETUP_ACCOUNT = "setup_account"


class PaymentStep(BaseModel):
    """Internal representation of a single onboarding step and its status."""

    id: str = Field(description="Step identifier")
    title: str = Field(description="Step title")
    description: str = Field(description="Step description")
    completed: bool = Field(description="Whether the step is completed")


class PaymentStatusResponse(BaseModel):
    """Aggregated payment-account status returned to callers."""

    payment_ready: bool = Field(
        description="Whether the workspace is ready to accept payments"
    )
    steps: list[PaymentStep] = Field(description="List of onboarding steps")
    workspace_status: WorkspaceStatus = Field(description="Current workspace status")


class WorkspaceDeletionCheckResult(BaseModel):
    """Pre-deletion check: lists resources that would block workspace removal."""

    can_delete_immediately: bool = Field(
        description="Whether the workspace can be deleted immediately"
    )
    blocked_reasons: list[WorkspaceDeletionBlockedReason] = Field(
        default_factory=list,
        description="Reasons why immediate deletion is blocked",
    )


# ── Error classes ──


class WorkspaceError(RapidlyError): ...


class InvalidAccount(WorkspaceError):
    def __init__(self, account_id: UUID) -> None:
        self.account_id = account_id
        message = (
            f"The account {account_id} does not exist or you don't have access to it."
        )
        super().__init__(message)


class PendingPaymentsExist(WorkspaceError):
    def __init__(self, workspace_slug: str) -> None:
        self.workspace_slug = workspace_slug
        message = (
            f"Cannot change the Stripe account for workspace '{workspace_slug}' "
            f"while there are pending payments. Wait for all payments to complete."
        )
        super().__init__(message, 409)


# ── Reads ──


async def list(
    session: AsyncReadSession,
    auth_subject: AuthPrincipal[User | Workspace],
    *,
    slug: str | None = None,
    pagination: PaginationParams,
    sorting: Sequence[Sorting[WorkspaceSortProperty]] = (
        (WorkspaceSortProperty.created_at, False),
    ),
) -> tuple[Sequence[Workspace], int]:
    repository = WorkspaceRepository.from_session(session)
    statement = repository.get_readable_statement(auth_subject)

    if slug is not None:
        statement = statement.where(Workspace.slug == slug)

    statement = repository.apply_sorting(statement, sorting)

    return await repository.paginate(
        statement, limit=pagination.limit, page=pagination.page
    )


async def get(
    session: AsyncReadSession,
    auth_subject: AuthPrincipal[User | Workspace],
    id: uuid.UUID,
    *,
    options: Options = (),
) -> Workspace | None:
    repository = WorkspaceRepository.from_session(session)
    statement = (
        repository.get_readable_statement(auth_subject)
        .where(Workspace.id == id)
        .options(*options)
    )
    return await repository.get_one_or_none(statement)


async def get_anonymous(
    session: AsyncReadSession,
    id: uuid.UUID,
    *,
    options: Options = (),
) -> Workspace | None:
    """Retrieve an workspace without authentication — restricted to public fields only."""
    repository = WorkspaceRepository.from_session(session)
    statement = (
        repository.get_base_statement()
        .where(Workspace.blocked_at.is_(None))
        .where(Workspace.id == id)
        .options(*options)
    )

    return await repository.get_one_or_none(statement)


async def get_admin_user(
    session: AsyncReadSession,
    workspace: Workspace,
) -> User | None:
    """Get the admin user of the workspace from the associated account."""
    repo = WorkspaceRepository.from_session(session)
    return await repo.get_admin_user(session, workspace)


async def resolve_workspace_for_payment_status(
    session: AsyncReadSession,
    auth_subject: AuthPrincipal[Any],
    workspace_id: uuid.UUID,
    *,
    account_verification_only: bool = False,
) -> Workspace | None:
    """Look up the workspace for a payment-status check, applying auth rules.

    Anonymous callers may only query when *account_verification_only* is set.
    Authenticated callers must hold at least one of the workspace read/write scopes.
    """
    from sqlalchemy.orm import joinedload as _jl

    from rapidly.errors import ResourceNotFound, Unauthorized
    from rapidly.identity.auth.models import is_anonymous_principal
    from rapidly.identity.auth.scope import Scope

    eager = (_jl(Workspace.account).joinedload(Account.admin),)

    if is_anonymous_principal(auth_subject):
        if not account_verification_only:
            raise Unauthorized()
        return await get_anonymous(session, workspace_id, options=eager)

    required_scopes = {
        Scope.web_read,
        Scope.web_write,
        Scope.workspaces_read,
        Scope.workspaces_write,
    }
    if not (auth_subject.scopes & required_scopes):
        raise ResourceNotFound()

    return await get(session, auth_subject, workspace_id, options=eager)


async def list_members_with_admin_flag(
    session: AsyncReadSession,
    workspace: Workspace,
    workspace_id: uuid.UUID,
) -> Sequence[Any]:
    """List workspace members with is_admin flag set on the admin user."""
    from rapidly.platform.workspace_membership import (
        actions as workspace_membership_service,
    )
    from rapidly.platform.workspace_membership.types import WorkspaceMember

    all_members = await workspace_membership_service.list_by_workspace(
        session, workspace_id
    )
    admin_user = await get_admin_user(session, workspace)
    admin_user_id = admin_user.id if admin_user else None

    member_items: builtins.list[WorkspaceMember] = []
    for m in all_members:
        member_data = WorkspaceMember.model_validate(m)
        if admin_user_id and m.user_id == admin_user_id:
            member_data.is_admin = True
        member_items.append(member_data)

    return member_items


async def get_review_status(
    session: AsyncReadSession,
    workspace_id: uuid.UUID,
) -> WorkspaceReview | None:
    """Get the review record for a workspace."""
    repo = WorkspaceReviewRepository.from_session(session)
    return await repo.get_by_workspace(workspace_id)


# ── Writes ──


async def create(
    session: AsyncSession,
    create_schema: WorkspaceCreate,
    auth_subject: AuthPrincipal[User],
) -> Workspace:
    repository = WorkspaceRepository.from_session(session)
    if await repository.slug_exists(create_schema.slug):
        raise RequestValidationError(
            [
                validation_error(
                    "slug",
                    "An workspace with this slug already exists.",
                    create_schema.slug,
                )
            ]
        )

    create_data = create_schema.model_dump(exclude_unset=True, exclude_none=True)
    feature_settings = create_data.get("feature_settings", {})
    feature_settings["member_model_enabled"] = True
    create_data["feature_settings"] = feature_settings

    workspace = await repository.create(
        Workspace(
            **create_data,
            customer_invoice_prefix=create_schema.slug.upper(),
        )
    )
    await add_user(session, workspace, auth_subject.subject)

    dispatch_task("workspace.created", workspace_id=workspace.id)

    posthog.auth_subject_event(
        auth_subject,
        "workspaces",
        "create",
        "done",
        {
            "id": workspace.id,
            "name": workspace.name,
            "slug": workspace.slug,
        },
    )
    return workspace


async def update(
    session: AsyncSession,
    workspace: Workspace,
    update_schema: WorkspaceUpdate,
) -> Workspace:
    repository = WorkspaceRepository.from_session(session)

    if workspace.onboarded_at is None:
        workspace.onboarded_at = datetime.now(UTC)

    if update_schema.feature_settings is not None:
        workspace.feature_settings = {
            **workspace.feature_settings,
            **update_schema.feature_settings.model_dump(
                mode="json", exclude_unset=True, exclude_none=True
            ),
        }

    if update_schema.notification_settings is not None:
        workspace.notification_settings = update_schema.notification_settings

    previous_details = workspace.details
    update_dict = update_schema.model_dump(
        by_alias=True,
        exclude_unset=True,
        exclude={
            "profile_settings",
            "feature_settings",
            "details",
        },
    )

    # Only store details once to avoid API overrides later w/o review
    if not previous_details and update_schema.details:
        workspace.details = update_schema.details.model_dump()
        workspace.details_submitted_at = datetime.now(UTC)

    workspace = await repository.update(workspace, update_dict=update_dict)

    await _after_update(session, workspace)
    return workspace


# ── Deletion ──


def _build_pii_anonymization_dict(
    workspace: Workspace,
    *,
    include_slug: bool = False,
) -> dict[str, Any]:
    """Build an update dict that anonymizes PII fields on a workspace."""
    update_dict: dict[str, Any] = {}

    pii_fields = ["name", "website", "customer_invoice_prefix"]
    if include_slug:
        pii_fields.append("slug")
    github_fields = ["bio", "company", "blog", "location", "twitter_username"]
    for pii_field in pii_fields + github_fields:
        value = getattr(workspace, pii_field)
        if value:
            update_dict[pii_field] = anonymize_for_deletion(value)

    if workspace.email:
        update_dict["email"] = anonymize_email_for_deletion(workspace.email)

    if workspace._avatar_url:
        update_dict["avatar_url"] = (
            "https://avatars.githubusercontent.com/u/105373340?s=48&v=4"
        )
    if workspace.details:
        update_dict["details"] = {}

    if workspace.socials:
        update_dict["socials"] = []

    return update_dict


async def delete(
    session: AsyncSession,
    workspace: Workspace,
) -> Workspace:
    """Anonymizes fields on the Workspace that can contain PII and then
    soft-deletes the Workspace.

    DOES NOT:
    - Delete or anonymize Users related to the Workspace
    - Delete or anonymize Account of the Workspace
    - Delete or anonymize Customers or Products of the Workspace
    - Remove API tokens (workspace or personal)
    """
    repository = WorkspaceRepository.from_session(session)
    update_dict = _build_pii_anonymization_dict(workspace, include_slug=True)
    workspace = await repository.update(workspace, update_dict=update_dict)
    await repository.soft_delete(workspace)

    return workspace


async def request_deletion(
    session: AsyncSession,
    auth_subject: AuthPrincipal[User],
    workspace: Workspace,
) -> WorkspaceDeletionCheckResult:
    """Request deletion of an workspace.

    Authorization:
    - If the workspace has an account, only the account admin can delete
    - If there is no account, any workspace member can delete

    Flow:
    1. Check authorization
    2. If has account -> try to delete Stripe account
    3. If Stripe deletion fails -> create support ticket
    4. Soft delete workspace
    """
    # Authorization check: only account admin can delete if account exists
    if workspace.account_id is not None:
        is_admin = await account_service.is_user_admin(
            session, workspace.account_id, auth_subject.subject
        )
        if not is_admin:
            raise NotPermitted(
                "Only the account admin can delete an workspace with an account"
            )

    # Workspace is eligible for deletion
    # If it has an account, try to delete it first
    if workspace.account_id is not None:
        try:
            await _delete_account(session, workspace)
        except Exception as e:
            _log.error(
                "workspace.deletion.stripe_account_deletion_failed",
                workspace_id=workspace.id,
                error=str(e),
            )
            # Stripe deletion failed, create support ticket
            check_result = WorkspaceDeletionCheckResult(
                can_delete_immediately=False,
                blocked_reasons=[
                    WorkspaceDeletionBlockedReason.STRIPE_ACCOUNT_DELETION_FAILED
                ],
            )
            dispatch_task(
                "workspace.deletion_requested",
                workspace_id=workspace.id,
                user_id=auth_subject.subject.id,
                blocked_reasons=[r.value for r in check_result.blocked_reasons],
            )
            return check_result

    # Soft delete the workspace
    await soft_delete_workspace(session, workspace)

    return WorkspaceDeletionCheckResult(
        can_delete_immediately=True,
        blocked_reasons=[],
    )


async def soft_delete_workspace(
    session: AsyncSession,
    workspace: Workspace,
) -> Workspace:
    """Soft-delete an workspace, preserving the slug for admin links.

    Anonymizes PII fields (except slug) and sets deleted_at timestamp.
    """
    repository = WorkspaceRepository.from_session(session)
    update_dict = _build_pii_anonymization_dict(workspace, include_slug=False)
    workspace = await repository.update(workspace, update_dict=update_dict)
    await repository.soft_delete(workspace)

    _log.info(
        "workspace.deleted",
        workspace_id=workspace.id,
        slug=workspace.slug,
    )

    return workspace


async def _delete_account(
    session: AsyncSession,
    workspace: Workspace,
) -> None:
    """Delete the Stripe account linked to an workspace."""
    if workspace.account_id is None:
        return

    account_repository = AccountRepository.from_session(session)
    account = await account_repository.get_by_id(workspace.account_id)

    if account is None:
        return

    if account.stripe_id:
        await account_service.delete_stripe_account(session, account)

    repository = WorkspaceRepository.from_session(session)
    await repository.update(workspace, update_dict={"account_id": None})

    await account_service.delete(session, account)

    _log.info(
        "workspace.account_deleted",
        workspace_id=workspace.id,
        account_id=account.id,
    )


# ── Membership ──


async def add_user(
    session: AsyncSession,
    workspace: Workspace,
    user: User,
) -> None:
    repository = WorkspaceRepository.from_session(session)
    membership_repo = WorkspaceMembershipRepository.from_session(session)
    nested = await session.begin_nested()
    try:
        relation = WorkspaceMembership(user_id=user.id, workspace_id=workspace.id)
        await membership_repo.create(relation, flush=True)
        _log.info(
            "workspace.add_user.created",
            user_id=user.id,
            workspace_id=workspace.id,
        )
    except IntegrityError:
        # TODO: Currently, we treat this as success since the connection
        # exists. However, once we use status to distinguish active/inactive
        # installations we need to change this.
        _log.info(
            "workspace.add_user.already_exists",
            workspace_id=workspace.id,
            user_id=user.id,
        )
        await nested.rollback()
        await repository.reactivate_membership(user.id, workspace.id)


async def invite_member(
    session: AsyncSession,
    workspace: Workspace,
    email: str,
    inviter_email: str,
) -> tuple[WorkspaceMembership, bool]:
    """Invite a user to join a workspace by email.

    Creates or fetches the user, adds them to the workspace, and sends
    an invitation email.  Returns ``(membership, created)`` where
    *created* is ``True`` when a new membership was made.
    """
    from rapidly.platform.user import actions as user_service

    user, _ = await user_service.get_by_email_or_create(session, email)

    membership_repo = WorkspaceMembershipRepository.from_session(session)
    existing = await membership_repo.get_by_user_and_org(user.id, workspace.id)
    if existing is not None:
        return existing, False

    await add_user(session, workspace, user)

    body = render_email_template(
        WorkspaceInviteEmail(
            props=WorkspaceInviteProps(
                email=email,
                workspace_name=workspace.name,
                inviter_email=inviter_email or "",
                invite_url=settings.generate_frontend_url(
                    f"/dashboard/{workspace.slug}"
                ),
            )
        )
    )
    enqueue_email(
        to_email_addr=email,
        subject=f"You've been invited to {workspace.name} on Rapidly",
        html_content=body,
    )

    membership = await membership_repo.get_by_user_and_org(user.id, workspace.id)
    if membership is None:
        raise ValueError("Failed to create workspace membership")
    return membership, True


async def leave(
    session: AsyncSession,
    workspace: Workspace,
    user: User,
) -> None:
    """Remove a user from a workspace (self-service leave).

    Raises ``NotPermitted`` if the user is the admin or the only member.
    """
    admin_user = await get_admin_user(session, workspace)
    if admin_user and admin_user.id == user.id:
        raise NotPermitted("Workspace admins cannot leave the workspace.")

    membership_repo = WorkspaceMembershipRepository.from_session(session)
    member_count = await membership_repo.get_member_count(workspace.id)
    if member_count <= 1:
        raise NotPermitted("Cannot leave workspace as the only member.")

    await membership_repo.remove_member(user.id, workspace.id)


# ── Onboarding ──


async def set_account(
    session: AsyncSession,
    auth_subject: AuthPrincipal[User | Workspace],
    workspace: Workspace,
    account_id: UUID,
    *,
    skip_pending_check: bool = False,
) -> Workspace:
    # If switching to a different account, check for pending payments
    if workspace.account_id is not None and workspace.account_id != account_id:
        if not skip_pending_check and await _has_pending_payments(
            session, workspace.id
        ):
            raise PendingPaymentsExist(workspace.slug)
        # The old account is NOT disconnected — it stays available for
        # the user to switch back to later via the accounts list.

    account = await account_service.get(session, auth_subject, account_id)
    if account is None:
        raise InvalidAccount(account_id)

    repository = WorkspaceRepository.from_session(session)
    workspace = await repository.update(workspace, update_dict={"account": account})

    dispatch_task("workspace.account_set", workspace.id)

    await _after_update(session, workspace)

    return workspace


async def _has_pending_payments(
    session: AsyncSession,
    workspace_id: UUID,
) -> bool:
    """Check if the workspace has any pending payments that would block account switching."""
    from sqlalchemy import exists, select

    from rapidly.models.file_share_payment import (
        FileSharePayment,
        FileSharePaymentStatus,
    )
    from rapidly.models.file_share_session import FileShareSession
    from rapidly.models.payment import Payment, PaymentStatus

    # Check FileSharePayments via sessions in this workspace
    pending_fsp = await session.scalar(
        select(
            exists(
                select(FileSharePayment.id)
                .join(
                    FileShareSession, FileSharePayment.session_id == FileShareSession.id
                )
                .where(
                    FileShareSession.workspace_id == workspace_id,
                    FileSharePayment.status == FileSharePaymentStatus.pending,
                )
            )
        )
    )
    if pending_fsp:
        return True

    # Check Payment records
    pending_payment = await session.scalar(
        select(
            exists(
                select(Payment.id).where(
                    Payment.workspace_id == workspace_id,
                    Payment.status == PaymentStatus.pending,
                )
            )
        )
    )
    return bool(pending_payment)


async def _after_update(
    session: AsyncSession,
    workspace: Workspace,
) -> None:
    await webhook_service.send(
        session, workspace, WebhookEventType.workspace_updated, workspace
    )


# ── Review ──


async def confirm_workspace_reviewed(
    session: AsyncSession,
    workspace: Workspace,
    next_review_threshold: int,
) -> Workspace:
    repository = WorkspaceRepository.from_session(session)

    update_dict: dict[str, Any] = {
        "status": WorkspaceStatus.ACTIVE,
        "status_updated_at": datetime.now(UTC),
        "next_review_threshold": next_review_threshold,
    }

    initial_review = False
    if workspace.initially_reviewed_at is None:
        update_dict["initially_reviewed_at"] = datetime.now(UTC)
        initial_review = True

    workspace = await repository.update(workspace, update_dict=update_dict)
    await repository.sync_account_status(workspace)

    # If there's a pending appeal, mark it as approved
    review_repository = WorkspaceReviewRepository.from_session(session)
    review = await review_repository.get_by_workspace(workspace.id)
    if review and review.appeal_submitted_at and review.appeal_decision is None:
        await review_repository.update(
            review,
            update_dict={
                "appeal_decision": WorkspaceReview.AppealDecision.APPROVED,
                "appeal_reviewed_at": datetime.now(UTC),
            },
        )

    dispatch_task(
        "workspace.reviewed",
        workspace_id=workspace.id,
        initial_review=initial_review,
    )
    return workspace


async def deny_workspace(session: AsyncSession, workspace: Workspace) -> Workspace:
    repository = WorkspaceRepository.from_session(session)
    workspace = await repository.update(
        workspace,
        update_dict={
            "status": WorkspaceStatus.DENIED,
            "status_updated_at": datetime.now(UTC),
        },
    )
    await repository.sync_account_status(workspace)

    # If there's a pending appeal, mark it as rejected
    review_repository = WorkspaceReviewRepository.from_session(session)
    review = await review_repository.get_by_workspace(workspace.id)
    if review and review.appeal_submitted_at and review.appeal_decision is None:
        await review_repository.update(
            review,
            update_dict={
                "appeal_decision": WorkspaceReview.AppealDecision.REJECTED,
                "appeal_reviewed_at": datetime.now(UTC),
            },
        )

    return workspace


async def set_workspace_under_review(
    session: AsyncSession, workspace: Workspace
) -> Workspace:
    repository = WorkspaceRepository.from_session(session)
    workspace = await repository.update(
        workspace,
        update_dict={
            "status": WorkspaceStatus.ONGOING_REVIEW,
            "status_updated_at": datetime.now(UTC),
        },
    )
    await repository.sync_account_status(workspace)
    dispatch_task("workspace.under_review", workspace_id=workspace.id)
    return workspace


async def update_status_from_stripe_account(
    session: AsyncSession, account: Account
) -> None:
    """Update workspace status based on Stripe account capabilities."""
    repository = WorkspaceRepository.from_session(session)
    workspaces = await repository.get_all_by_account(account.id)

    for workspace in workspaces:
        # Don't override workspaces that are denied
        if workspace.status == WorkspaceStatus.DENIED:
            continue

        update_dict: dict[str, Any] = {}

        # If account is fully set up, set workspace to ACTIVE
        if all(
            (
                not workspace.is_under_review,
                not workspace.is_active(),
                account.currency is not None,
                account.is_details_submitted,
                account.is_charges_enabled,
                account.is_payouts_enabled,
            )
        ):
            update_dict["status"] = WorkspaceStatus.ACTIVE
            update_dict["status_updated_at"] = datetime.now(UTC)

        # If Stripe disables some capabilities, reset to ONBOARDING_STARTED
        if any(
            (
                not account.is_details_submitted,
                not account.is_charges_enabled,
                not account.is_payouts_enabled,
            )
        ):
            update_dict["status"] = WorkspaceStatus.ONBOARDING_STARTED
            update_dict["status_updated_at"] = datetime.now(UTC)

        if update_dict:
            workspace = await repository.update(workspace, update_dict=update_dict)
        await repository.sync_account_status(workspace)


async def _sync_account_status(session: AsyncSession, workspace: Workspace) -> None:
    """Sync workspace account status flags from Stripe.

    Thin wrapper kept for call-sites that don't already have a repository instance.
    """
    repository = WorkspaceRepository.from_session(session)
    await repository.sync_account_status(workspace)


async def get_payment_status(
    session: AsyncReadSession,
    workspace: Workspace,
    account_verification_only: bool = False,
) -> PaymentStatusResponse:
    """Get payment status for an workspace (Stripe account setup)."""
    from rapidly.catalog.share.queries import ShareRepository
    from rapidly.platform.workspace_access_token.queries import (
        WorkspaceAccessTokenRepository,
    )

    # Check grandfathering
    cutoff_date = _GRANDFATHERING_CUTOFF
    is_grandfathered = workspace.created_at <= cutoff_date

    account_setup_complete = _is_account_setup_complete(workspace)

    if account_verification_only:
        steps = [
            PaymentStep(
                id=PaymentStepID.SETUP_ACCOUNT,
                title="Finish account setup",
                description="Complete your account details and verify your identity",
                completed=account_setup_complete,
            )
        ]
    else:
        share_repository = ShareRepository.from_session(session)
        share_count = await share_repository.count_by_workspace_id(workspace.id)
        has_product = share_count > 0

        token_repository = WorkspaceAccessTokenRepository.from_session(session)
        api_key_count = await token_repository.count_by_workspace_id(workspace.id)
        has_api_key = api_key_count > 0

        steps = [
            PaymentStep(
                id=PaymentStepID.CREATE_PRODUCT,
                title="Create a share",
                description="Create your first file share to start accepting payments",
                completed=has_product,
            ),
            PaymentStep(
                id=PaymentStepID.INTEGRATE_API,
                title="Set up API integration",
                description="Create an API key to integrate with your application",
                completed=has_api_key,
            ),
            PaymentStep(
                id=PaymentStepID.SETUP_ACCOUNT,
                title="Finish account setup",
                description="Complete your account details and verify your identity",
                completed=account_setup_complete,
            ),
        ]

    if is_grandfathered:
        payment_ready = True
    elif settings.ENV in (Environment.development, Environment.sandbox):
        payment_ready = workspace.account_id is not None
    else:
        payment_ready = all(step.completed for step in steps)

    return PaymentStatusResponse(
        payment_ready=payment_ready,
        steps=steps,
        workspace_status=workspace.status,
    )


def _is_account_setup_complete(workspace: Workspace) -> bool:
    """Check if the workspace's account setup is complete."""
    if not workspace.account_id:
        return False

    account = workspace.account
    if not account:
        return False

    return account.stripe_id is not None and account.is_details_submitted


async def is_workspace_ready_for_payment(
    session: AsyncReadSession, workspace: Workspace
) -> bool:
    """
    Check if a workspace is ready to accept payments.
    This method loads the account and admin data as needed, avoiding the need
    for eager loading in other services.
    """
    # In sandbox environment, always allow payments regardless of account setup
    if settings.ENV == Environment.sandbox:
        return True

    # First check basic conditions that don't require account data
    if workspace.is_blocked() or workspace.status == WorkspaceStatus.DENIED:
        return False

    # Check grandfathering - if grandfathered, they're ready
    cutoff_date = _GRANDFATHERING_CUTOFF
    if workspace.created_at <= cutoff_date:
        return True

    # For new workspaces, check basic conditions first
    if workspace.status not in WorkspaceStatus.payment_ready_statuses():
        return False

    # Details must be submitted (check for empty dict as well)
    if not workspace.details_submitted_at or not workspace.details:
        return False

    # Must have an active payout account
    if workspace.account_id is None:
        return False

    account_repository = AccountRepository.from_session(session)
    account = await account_repository.get_by_id(
        workspace.account_id, options=(joinedload(Account.admin),)
    )
    if not account:
        return False

    # Check admin identity verification status
    admin = account.admin
    if not admin or admin.identity_verification_status not in [
        IdentityVerificationStatus.verified,
        IdentityVerificationStatus.pending,
    ]:
        return False

    return True


async def validate_with_ai(
    session: AsyncSession, workspace: Workspace
) -> WorkspaceReview:
    """Validate workspace details using AI and store the result."""
    repository = WorkspaceReviewRepository.from_session(session)
    previous_validation = await repository.get_by_workspace(workspace.id)

    if previous_validation is not None:
        return previous_validation

    result = await workspace_validator.validate_workspace_details(workspace)

    ai_validation = WorkspaceReview(
        workspace_id=workspace.id,
        verdict=result.verdict.verdict,
        risk_score=result.verdict.risk_score,
        violated_sections=result.verdict.violated_sections,
        reason=result.verdict.reason,
        timed_out=result.timed_out,
        workspace_details_snapshot={
            "name": workspace.name,
            "website": workspace.website,
            "details": workspace.details,
            "socials": workspace.socials,
        },
        model_used=workspace_validator.model.model_name,
    )

    if result.verdict.verdict in ["FAIL", "UNCERTAIN"]:
        await deny_workspace(session, workspace)

    await repository.create(ai_validation)

    return ai_validation


# ── Appeals ──


async def submit_appeal(
    session: AsyncSession, workspace: Workspace, appeal_reason: str
) -> WorkspaceReview:
    """Submit an appeal for workspace review."""

    repository = WorkspaceReviewRepository.from_session(session)
    review = await repository.get_by_workspace(workspace.id)

    if review is None:
        raise ValueError("Workspace must have a review before submitting appeal")

    if review.verdict == WorkspaceReview.Verdict.PASS:
        raise ValueError("Cannot submit appeal for a passed review")

    if review.appeal_submitted_at is not None:
        raise ValueError("Appeal has already been submitted for this workspace")

    review = await repository.update(
        review,
        update_dict={
            "appeal_submitted_at": datetime.now(UTC),
            "appeal_reason": appeal_reason,
        },
    )

    return review


async def approve_appeal(
    session: AsyncSession, workspace: Workspace
) -> WorkspaceReview:
    """Approve an workspace's appeal and restore payment access."""

    review_repository = WorkspaceReviewRepository.from_session(session)
    review = await review_repository.get_by_workspace(workspace.id)

    if review is None:
        raise ValueError("Workspace must have a review before approving appeal")

    if review.appeal_submitted_at is None:
        raise ValueError("No appeal has been submitted for this workspace")

    if review.appeal_decision is not None:
        raise ValueError("Appeal has already been reviewed")

    workspace_repository = WorkspaceRepository.from_session(session)
    workspace = await workspace_repository.update(
        workspace,
        update_dict={
            "status": WorkspaceStatus.ACTIVE,
            "status_updated_at": datetime.now(UTC),
        },
    )
    review = await review_repository.update(
        review,
        update_dict={
            "appeal_decision": WorkspaceReview.AppealDecision.APPROVED,
            "appeal_reviewed_at": datetime.now(UTC),
        },
    )

    await _sync_account_status(session, workspace)

    return review


async def deny_appeal(session: AsyncSession, workspace: Workspace) -> WorkspaceReview:
    """Deny an workspace's appeal and keep payment access blocked."""

    repository = WorkspaceReviewRepository.from_session(session)
    review = await repository.get_by_workspace(workspace.id)

    if review is None:
        raise ValueError("Workspace must have a review before denying appeal")

    if review.appeal_submitted_at is None:
        raise ValueError("No appeal has been submitted for this workspace")

    if review.appeal_decision is not None:
        raise ValueError("Appeal has already been reviewed")

    review = await repository.update(
        review,
        update_dict={
            "appeal_decision": WorkspaceReview.AppealDecision.REJECTED,
            "appeal_reviewed_at": datetime.now(UTC),
        },
    )

    return review


async def mark_ai_onboarding_complete(
    session: AsyncSession, workspace: Workspace
) -> Workspace:
    """Mark the AI onboarding as completed for this workspace.

    Only sets the timestamp if it hasn't been set before, to capture the first completion.
    """
    if workspace.ai_onboarding_completed_at is not None:
        return workspace

    repository = WorkspaceRepository.from_session(session)
    workspace = await repository.update(
        workspace,
        update_dict={
            "onboarded_at": datetime.now(UTC),
            "ai_onboarding_completed_at": datetime.now(UTC),
        },
    )
    return workspace
