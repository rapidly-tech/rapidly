"""Background jobs for workspace lifecycle: onboarding, review, and cleanup.

Includes account-creation triggers, AI-powered workspace validation,
review-threshold checks, and periodic cleanup of soft-deleted records.
"""

import uuid

from sqlalchemy.orm import joinedload

from rapidly.billing.account.queries import AccountRepository
from rapidly.errors import BackgroundTaskError
from rapidly.messaging.email.react import render_email_template
from rapidly.messaging.email.sender import enqueue_email
from rapidly.messaging.email.types import (
    WorkspaceReviewedEmail,
    WorkspaceReviewedProps,
    WorkspaceUnderReviewEmail,
    WorkspaceUnderReviewProps,
)
from rapidly.models import Workspace
from rapidly.models.workspace import WorkspaceStatus
from rapidly.platform.user.queries import UserRepository
from rapidly.worker import AsyncSessionMaker, TaskPriority, actor

from .queries import WorkspaceRepository


class WorkspaceTaskError(BackgroundTaskError): ...


class WorkspaceDoesNotExist(WorkspaceTaskError):
    def __init__(self, workspace_id: uuid.UUID) -> None:
        self.workspace_id = workspace_id
        message = f"The workspace with id {workspace_id} does not exist."
        super().__init__(message)


class WorkspaceAccountNotSet(WorkspaceTaskError):
    def __init__(self, workspace_id: uuid.UUID) -> None:
        self.workspace_id = workspace_id
        message = f"The workspace with id {workspace_id} does not have an account set."
        super().__init__(message)


class AccountDoesNotExist(WorkspaceTaskError):
    def __init__(self, account_id: uuid.UUID) -> None:
        self.account_id = account_id
        message = f"The account with id {account_id} does not exist."
        super().__init__(message)


class UserDoesNotExist(WorkspaceTaskError):
    def __init__(self, user_id: uuid.UUID) -> None:
        self.user_id = user_id
        message = f"The user with id {user_id} does not exist."
        super().__init__(message)


# ── Stripe sync ──


@actor(actor_name="workspace.created", priority=TaskPriority.LOW)
async def workspace_created(workspace_id: uuid.UUID) -> None:
    async with AsyncSessionMaker() as session:
        repository = WorkspaceRepository.from_session(session)
        workspace = await repository.get_by_id(workspace_id)
        if workspace is None:
            raise WorkspaceDoesNotExist(workspace_id)


@actor(actor_name="workspace.account_set", priority=TaskPriority.LOW)
async def workspace_account_set(workspace_id: uuid.UUID) -> None:
    async with AsyncSessionMaker() as session:
        repository = WorkspaceRepository.from_session(session)
        workspace = await repository.get_by_id(workspace_id)
        if workspace is None:
            raise WorkspaceDoesNotExist(workspace_id)

        if workspace.account_id is None:
            raise WorkspaceAccountNotSet(workspace_id)

        account_repository = AccountRepository.from_session(session)
        account = await account_repository.get_by_id(workspace.account_id)
        if account is None:
            raise AccountDoesNotExist(workspace.account_id)


# ── Notifications ──


@actor(actor_name="workspace.under_review", priority=TaskPriority.LOW)
async def workspace_under_review(workspace_id: uuid.UUID) -> None:
    async with AsyncSessionMaker() as session:
        repository = WorkspaceRepository.from_session(session)
        workspace = await repository.get_by_id(
            workspace_id, options=(joinedload(Workspace.account),)
        )
        if workspace is None:
            raise WorkspaceDoesNotExist(workspace_id)

        # Send an email for the initial review
        if workspace.status == WorkspaceStatus.INITIAL_REVIEW:
            admin_user = await repository.get_admin_user(session, workspace)
            if admin_user:
                email = WorkspaceUnderReviewEmail(
                    props=WorkspaceUnderReviewProps.model_validate(
                        {"email": admin_user.email, "workspace": workspace}
                    )
                )
                enqueue_email(
                    to_email_addr=admin_user.email,
                    subject="Your workspace is under review",
                    html_content=render_email_template(email),
                )


@actor(actor_name="workspace.reviewed", priority=TaskPriority.LOW)
async def workspace_reviewed(
    workspace_id: uuid.UUID, initial_review: bool = False
) -> None:
    async with AsyncSessionMaker() as session:
        repository = WorkspaceRepository.from_session(session)
        workspace = await repository.get_by_id(workspace_id)
        if workspace is None:
            raise WorkspaceDoesNotExist(workspace_id)

        # Send an email after the initial review
        if initial_review:
            admin_user = await repository.get_admin_user(session, workspace)
            if admin_user:
                email = WorkspaceReviewedEmail(
                    props=WorkspaceReviewedProps.model_validate(
                        {"email": admin_user.email, "workspace": workspace}
                    )
                )
                enqueue_email(
                    to_email_addr=admin_user.email,
                    subject="Your workspace review is complete",
                    html_content=render_email_template(email),
                )


@actor(actor_name="workspace.deletion_requested", priority=TaskPriority.HIGH)
async def workspace_deletion_requested(
    workspace_id: uuid.UUID,
    user_id: uuid.UUID,
    blocked_reasons: list[str],
) -> None:
    """Handle workspace deletion request that requires support review."""
    async with AsyncSessionMaker() as session:
        repository = WorkspaceRepository.from_session(session)
        workspace = await repository.get_by_id(workspace_id)
        if workspace is None:
            raise WorkspaceDoesNotExist(workspace_id)

        user_repository = UserRepository.from_session(session)
        user = await user_repository.get_by_id(user_id)
        if user is None:
            raise UserDoesNotExist(user_id)
