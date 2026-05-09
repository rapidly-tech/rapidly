"""Notification-recipient service: CRUD and preference management.

Manages the list of users or integrations that receive notifications
for a given workspace, including push-token registration and
per-channel enable / disable toggles.
"""

from collections.abc import Sequence
from uuid import UUID

from rapidly.errors import RequestValidationError, ValidationError, validation_error
from rapidly.identity.auth.models import AuthPrincipal
from rapidly.models.notification_recipient import NotificationRecipient
from rapidly.models.user import User
from rapidly.postgres import AsyncReadSession, AsyncSession

from .queries import NotificationRecipientRepository
from .types import (
    NotificationRecipientCreate,
    NotificationRecipientPlatform,
)


async def list_by_user(
    session: AsyncReadSession,
    user_id: UUID,
    expo_push_token: str | None,
    platform: NotificationRecipientPlatform | None,
) -> Sequence[NotificationRecipient]:
    repository = NotificationRecipientRepository.from_session(session)
    return await repository.list_by_user(
        user_id, expo_push_token=expo_push_token, platform=platform
    )


async def create(
    session: AsyncSession,
    notification_recipient_create: NotificationRecipientCreate,
    auth_subject: AuthPrincipal[User],
) -> NotificationRecipient:
    repository = NotificationRecipientRepository.from_session(session)

    errors: list[ValidationError] = []

    if await repository.get_by_expo_token(
        notification_recipient_create.expo_push_token
    ):
        errors.append(
            validation_error(
                "expo_push_token",
                "A notification recipient with this Expo push token already exists.",
                notification_recipient_create.expo_push_token,
            )
        )

    if errors:
        raise RequestValidationError(errors)

    return await repository.create(
        NotificationRecipient(
            user_id=auth_subject.subject.id,
            platform=notification_recipient_create.platform,
            expo_push_token=notification_recipient_create.expo_push_token,
        ),
        flush=True,
    )


async def delete(
    session: AsyncSession, auth_subject: AuthPrincipal[User], id: UUID
) -> None:
    repository = NotificationRecipientRepository.from_session(session)
    await repository.delete_for_user(id, auth_subject.subject.id)
