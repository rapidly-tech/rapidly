"""Workspace HTTP routes: CRUD, onboarding, invitations, and payment status.

Endpoints cover workspace lifecycle (create, update, delete), member
invitations, payment-readiness checks, account linking, and appeal
workflows.  All routes require an authenticated user with the appropriate
``workspaces:read`` or ``workspaces:write`` scope.
"""

from uuid import UUID

from fastapi import Body, Depends, Query, Response, status

from rapidly.billing.account import actions as account_service
from rapidly.billing.account.types import Account as AccountSchema
from rapidly.core.pagination import PaginatedList, PaginationParamsQuery
from rapidly.errors import (
    NotPermitted,
    RequestValidationError,
    ResourceNotFound,
    validation_error,
)
from rapidly.identity.auth.models import is_user_principal
from rapidly.models import Account, Workspace
from rapidly.openapi import APITag
from rapidly.platform.workspace_membership import (
    actions as workspace_membership_service,
)
from rapidly.platform.workspace_membership.types import (
    WorkspaceMember,
    WorkspaceMemberInvite,
)
from rapidly.postgres import (
    AsyncReadSession,
    AsyncSession,
    get_db_read_session,
    get_db_session,
)
from rapidly.routing import APIRouter

from . import actions as workspace_service
from . import ordering
from . import permissions as auth
from .types import Workspace as WorkspaceSchema
from .types import (
    WorkspaceAppealRequest,
    WorkspaceAppealResponse,
    WorkspaceCreate,
    WorkspaceDeletionResponse,
    WorkspaceID,
    WorkspacePaymentStatus,
    WorkspacePaymentStep,
    WorkspaceReviewStatus,
    WorkspaceUpdate,
)

router = APIRouter(prefix="/workspaces", tags=["workspaces"])

WorkspaceNotFound = {
    "description": "Workspace not found.",
    "model": ResourceNotFound.schema(),
}


# ── CRUD ──


@router.get(
    "/",
    summary="List Workspaces",
    response_model=PaginatedList[WorkspaceSchema],
    tags=[APITag.public],
)
async def list(
    auth_subject: auth.WorkspacesRead,
    pagination: PaginationParamsQuery,
    sorting: ordering.ListSorting,
    slug: str | None = Query(None, description="Filter by slug."),
    session: AsyncReadSession = Depends(get_db_read_session),
) -> PaginatedList[WorkspaceSchema]:
    """List workspaces."""
    results, count = await workspace_service.list(
        session,
        auth_subject,
        slug=slug,
        pagination=pagination,
        sorting=sorting,
    )

    return PaginatedList.from_paginated_results(
        [WorkspaceSchema.model_validate(result) for result in results],
        count,
        pagination,
    )


@router.get(
    "/{id}",
    summary="Get Workspace",
    response_model=WorkspaceSchema,
    responses={404: WorkspaceNotFound},
    tags=[APITag.public],
)
async def get(
    id: WorkspaceID,
    auth_subject: auth.WorkspacesRead,
    session: AsyncReadSession = Depends(get_db_read_session),
) -> Workspace:
    """Get an workspace by ID."""
    workspace = await workspace_service.get(session, auth_subject, id)

    if workspace is None:
        raise ResourceNotFound()

    return workspace


@router.post(
    "/",
    response_model=WorkspaceSchema,
    status_code=201,
    summary="Create Workspace",
    responses={201: {"description": "Workspace created."}},
    tags=[APITag.public],
)
async def create(
    workspace_create: WorkspaceCreate,
    auth_subject: auth.WorkspacesCreate,
    session: AsyncSession = Depends(get_db_session),
) -> Workspace:
    """Create an workspace."""
    return await workspace_service.create(session, workspace_create, auth_subject)


@router.patch(
    "/{id}",
    response_model=WorkspaceSchema,
    summary="Update Workspace",
    responses={
        200: {"description": "Workspace updated."},
        403: {
            "description": "You don't have the permission to update this workspace.",
            "model": NotPermitted.schema(),
        },
        404: WorkspaceNotFound,
    },
    tags=[APITag.public],
)
async def update(
    id: WorkspaceID,
    workspace_update: WorkspaceUpdate,
    auth_subject: auth.WorkspacesWrite,
    session: AsyncSession = Depends(get_db_session),
) -> Workspace:
    """Update an workspace."""
    workspace = await workspace_service.get(session, auth_subject, id)

    if workspace is None:
        raise ResourceNotFound()

    return await workspace_service.update(session, workspace, workspace_update)


@router.delete(
    "/{id}",
    response_model=WorkspaceDeletionResponse,
    summary="Delete Workspace",
    responses={
        200: {"description": "Workspace deleted or deletion request submitted."},
        403: {
            "description": "You don't have the permission to delete this workspace.",
            "model": NotPermitted.schema(),
        },
        404: WorkspaceNotFound,
    },
    tags=[APITag.private],
)
async def delete(
    id: WorkspaceID,
    auth_subject: auth.WorkspacesWriteUser,
    session: AsyncSession = Depends(get_db_session),
) -> WorkspaceDeletionResponse:
    """Request deletion of a workspace.

    If the workspace has no blocking resources, it will be immediately
    soft-deleted. If it has a Stripe account, that will be deleted first.

    If deletion cannot proceed immediately (e.g. Stripe deletion fails),
    a support ticket will be created for manual handling.
    """
    workspace = await workspace_service.get(session, auth_subject, id)

    if workspace is None:
        raise ResourceNotFound()

    result = await workspace_service.request_deletion(session, auth_subject, workspace)

    return WorkspaceDeletionResponse(
        deleted=result.can_delete_immediately,
        requires_support=not result.can_delete_immediately,
        blocked_reasons=result.blocked_reasons,
    )


# ── Payment setup ──


@router.get(
    "/{id}/account",
    response_model=AccountSchema,
    summary="Get Workspace Account",
    responses={
        403: {
            "description": "User is not the admin of the account.",
            "model": NotPermitted.schema(),
        },
        404: {
            "description": "Workspace not found or account not set.",
            "model": ResourceNotFound.schema(),
        },
    },
    tags=[APITag.private],
)
async def get_account(
    id: WorkspaceID,
    auth_subject: auth.WorkspacesRead,
    session: AsyncSession = Depends(get_db_session),
) -> Account:
    """Get the account for an workspace."""
    workspace = await workspace_service.get(session, auth_subject, id)

    if workspace is None:
        raise ResourceNotFound()

    if workspace.account_id is None:
        raise ResourceNotFound()

    if is_user_principal(auth_subject):
        user = auth_subject.subject
        if not await account_service.is_user_admin(session, workspace.account_id, user):
            raise NotPermitted("You are not the admin of this account")

    account = await account_service.get(session, auth_subject, workspace.account_id)
    if account is None:
        raise ResourceNotFound()

    # Sync account state from Stripe to pick up onboarding completion
    if account.stripe_id:
        await account_service.sync_from_stripe(session, account)

    return account


@router.post(
    "/{id}/switch-account",
    response_model=AccountSchema,
    summary="Switch Workspace Stripe Account",
    tags=[APITag.private],
)
async def switch_account(
    id: WorkspaceID,
    auth_subject: auth.WorkspacesWrite,
    account_id: UUID = Body(..., embed=True),
    session: AsyncSession = Depends(get_db_session),
) -> Account:
    """Switch the workspace's active Stripe account to an existing one."""
    workspace = await workspace_service.get(session, auth_subject, id)
    if workspace is None:
        raise ResourceNotFound()

    workspace = await workspace_service.set_account(
        session, auth_subject, workspace, account_id, skip_pending_check=True
    )

    if workspace.account_id is None:
        raise ResourceNotFound()
    account = await account_service.get(session, auth_subject, workspace.account_id)
    if account is None:
        raise ResourceNotFound()
    return account


@router.get(
    "/{id}/payment-status",
    response_model=WorkspacePaymentStatus,
    tags=[APITag.private],
    summary="Get Workspace Payment Status",
    responses={404: WorkspaceNotFound},
)
async def get_payment_status(
    id: WorkspaceID,
    auth_subject: auth.WorkspacesReadOrAnonymous,
    session: AsyncReadSession = Depends(get_db_read_session),
    account_verification_only: bool = Query(
        False,
        description="Only perform account verification checks, skip share and integration checks",
    ),
) -> WorkspacePaymentStatus:
    """Get payment status and onboarding steps for an workspace."""
    workspace = await workspace_service.resolve_workspace_for_payment_status(
        session, auth_subject, id, account_verification_only=account_verification_only
    )

    if workspace is None:
        raise ResourceNotFound()

    payment_status = await workspace_service.get_payment_status(
        session, workspace, account_verification_only=account_verification_only
    )

    return WorkspacePaymentStatus(
        payment_ready=payment_status.payment_ready,
        steps=[
            WorkspacePaymentStep(**step.model_dump()) for step in payment_status.steps
        ],
        workspace_status=payment_status.workspace_status,
    )


# ── Members ──


@router.get(
    "/{id}/members",
    response_model=PaginatedList[WorkspaceMember],
    tags=[APITag.private],
)
async def members(
    id: WorkspaceID,
    auth_subject: auth.WorkspacesRead,
    pagination: PaginationParamsQuery,
    session: AsyncReadSession = Depends(get_db_read_session),
) -> PaginatedList[WorkspaceMember]:
    """List members in an workspace."""
    workspace = await workspace_service.get(session, auth_subject, id)

    if workspace is None:
        raise ResourceNotFound()

    member_items = await workspace_service.list_members_with_admin_flag(
        session, workspace, id
    )

    return PaginatedList.from_paginated_results(
        member_items, len(member_items), pagination
    )


@router.post(
    "/{id}/members/invite",
    response_model=WorkspaceMember,
    status_code=201,
    tags=[APITag.private],
)
async def invite_member(
    id: WorkspaceID,
    invite_body: WorkspaceMemberInvite,
    auth_subject: auth.WorkspacesWrite,
    response: Response,
    session: AsyncSession = Depends(get_db_session),
) -> WorkspaceMember:
    """Invite a user to join an workspace."""
    workspace = await workspace_service.get(session, auth_subject, id)

    if workspace is None:
        raise ResourceNotFound()

    membership, created = await workspace_service.invite_member(
        session,
        workspace,
        email=invite_body.email,
        inviter_email=auth_subject.subject.email or "",
    )
    response.status_code = status.HTTP_201_CREATED if created else status.HTTP_200_OK
    return WorkspaceMember.model_validate(membership)


@router.delete(
    "/{id}/members/leave",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=[APITag.private],
    responses={
        204: {"description": "Successfully left the workspace."},
        403: {
            "description": "Cannot leave workspace (admin or only member).",
            "model": NotPermitted.schema(),
        },
        404: WorkspaceNotFound,
    },
)
async def leave_workspace(
    id: WorkspaceID,
    auth_subject: auth.WorkspacesWriteUser,
    session: AsyncSession = Depends(get_db_session),
) -> None:
    """Leave an workspace.

    Users can only leave an workspace if they are not the admin
    and there is at least one other member.
    """
    workspace = await workspace_service.get(session, auth_subject, id)

    if workspace is None:
        raise ResourceNotFound()

    await workspace_service.leave(session, workspace, auth_subject.subject)


@router.delete(
    "/{id}/members/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=[APITag.private],
    responses={
        204: {"description": "Member successfully removed."},
        403: {
            "description": "Not authorized to remove members.",
            "model": NotPermitted.schema(),
        },
        404: WorkspaceNotFound,
    },
)
async def remove_member(
    id: WorkspaceID,
    user_id: str,
    auth_subject: auth.WorkspacesWriteUser,
    session: AsyncSession = Depends(get_db_session),
) -> None:
    """Remove a member from an workspace.

    Only workspace admins can remove members.
    Admins cannot remove themselves.
    """
    from uuid import UUID as UUID_TYPE

    from rapidly.platform.workspace_membership.actions import (
        CannotRemoveWorkspaceAdmin,
        UserNotMemberOfWorkspace,
    )

    workspace = await workspace_service.get(session, auth_subject, id)
    if workspace is None:
        raise ResourceNotFound()

    admin_user = await workspace_service.get_admin_user(session, workspace)
    if not admin_user or admin_user.id != auth_subject.subject.id:
        raise NotPermitted("Only workspace admins can remove members.")

    try:
        target_user_id = UUID_TYPE(user_id)
    except ValueError:
        raise ResourceNotFound()

    try:
        await workspace_membership_service.remove_member_safe(
            session, target_user_id, workspace.id
        )
    except UserNotMemberOfWorkspace:
        raise ResourceNotFound()
    except CannotRemoveWorkspaceAdmin:
        raise NotPermitted("Cannot remove the workspace admin.")


# ── AI review & onboarding ──


@router.post(
    "/{id}/ai-validation",
    response_model=WorkspaceReviewStatus,
    summary="Validate Workspace Details with AI",
    responses={
        200: {"description": "Workspace validated with AI."},
        404: WorkspaceNotFound,
    },
    tags=[APITag.private],
)
async def validate_with_ai(
    id: WorkspaceID,
    auth_subject: auth.WorkspacesWrite,
    session: AsyncSession = Depends(get_db_session),
) -> WorkspaceReviewStatus:
    """Validate workspace details using AI compliance check."""
    workspace = await workspace_service.get(session, auth_subject, id)

    if workspace is None:
        raise ResourceNotFound()

    # Run AI validation and store results
    result = await workspace_service.validate_with_ai(session, workspace)

    return WorkspaceReviewStatus(
        verdict=result.verdict,
        reason=result.reason,
    )


@router.post(
    "/{id}/appeal",
    response_model=WorkspaceAppealResponse,
    status_code=201,
    summary="Submit Appeal for Workspace Review",
    responses={
        201: {"description": "Appeal submitted successfully."},
        404: WorkspaceNotFound,
        400: {"description": "Invalid appeal request."},
    },
    tags=[APITag.private],
)
async def submit_appeal(
    id: WorkspaceID,
    appeal_request: WorkspaceAppealRequest,
    auth_subject: auth.WorkspacesWrite,
    session: AsyncSession = Depends(get_db_session),
) -> WorkspaceAppealResponse:
    """Submit an appeal for workspace review after AI validation failure."""
    workspace = await workspace_service.get(session, auth_subject, id)

    if workspace is None:
        raise ResourceNotFound()

    try:
        result = await workspace_service.submit_appeal(
            session, workspace, appeal_request.reason
        )

        return WorkspaceAppealResponse(
            success=True,
            message="Appeal submitted successfully. Our team will review your case.",
            appeal_submitted_at=result.appeal_submitted_at,
        )
    except ValueError as e:
        raise RequestValidationError(
            [validation_error("reason", e.args[0], appeal_request.reason)]
        )


@router.post(
    "/{id}/ai-onboarding-complete",
    response_model=WorkspaceSchema,
    summary="Mark AI Onboarding Complete",
    responses={
        200: {"description": "AI onboarding marked as complete."},
        404: WorkspaceNotFound,
    },
    tags=[APITag.private],
)
async def mark_ai_onboarding_complete(
    id: WorkspaceID,
    auth_subject: auth.WorkspacesWrite,
    session: AsyncSession = Depends(get_db_session),
) -> Workspace:
    """Mark the AI onboarding as completed for this workspace."""
    workspace = await workspace_service.get(session, auth_subject, id)

    if workspace is None:
        raise ResourceNotFound()

    return await workspace_service.mark_ai_onboarding_complete(session, workspace)


@router.get(
    "/{id}/review-status",
    response_model=WorkspaceReviewStatus,
    summary="Get Workspace Review Status",
    responses={
        200: {"description": "Workspace review status retrieved."},
        404: WorkspaceNotFound,
    },
    tags=[APITag.private],
)
async def get_review_status(
    id: WorkspaceID,
    auth_subject: auth.WorkspacesRead,
    session: AsyncReadSession = Depends(get_db_read_session),
) -> WorkspaceReviewStatus:
    """Get the current review status and appeal information for an workspace."""
    workspace = await workspace_service.get(session, auth_subject, id)

    if workspace is None:
        raise ResourceNotFound()

    review = await workspace_service.get_review_status(session, workspace.id)

    if review is None:
        return WorkspaceReviewStatus()

    return WorkspaceReviewStatus(
        verdict=review.verdict,
        reason=review.reason,
        appeal_submitted_at=review.appeal_submitted_at,
        appeal_reason=review.appeal_reason,
        appeal_decision=review.appeal_decision,
        appeal_reviewed_at=review.appeal_reviewed_at,
    )
