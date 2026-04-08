"""Notification HTTP routes: reading, marking read, and recipient management.

Endpoints for listing user notifications, marking them as read (single
or bulk), and managing push-notification recipients (subscribe/list/delete
devices).
"""

from typing import Annotated

from fastapi import Depends, Path, Query
from pydantic import UUID4

from rapidly.core.pagination import PaginatedList, PaginationParamsQuery
from rapidly.messaging.notification_recipient import (
    actions as notification_recipient_service,
)
from rapidly.messaging.notification_recipient import (
    permissions as notification_recipient_auth,
)
from rapidly.messaging.notification_recipient.types import (
    NotificationRecipientCreate,
    NotificationRecipientPlatform,
    NotificationRecipientSchema,
)
from rapidly.messaging.notifications import (
    permissions as notifications_auth,
)
from rapidly.openapi import APITag
from rapidly.postgres import (
    AsyncReadSession,
    AsyncSession,
    get_db_read_session,
    get_db_session,
)
from rapidly.routing import APIRouter

from . import actions as notifications
from .types import NotificationsList, NotificationsMarkRead

NotificationRecipientID = Annotated[
    UUID4, Path(description="The notification recipient ID.")
]

router = APIRouter(tags=["notifications", APITag.private])


# ---------------------------------------------------------------------------
# Recipient management
# ---------------------------------------------------------------------------


@router.post(
    "/notifications/recipients",
    response_model=NotificationRecipientSchema,
    status_code=201,
    summary="Subscribes a device to notifications",
    responses={201: {"description": "Device subscribed to notifications."}},
)
async def create(
    notification_recipient_create: NotificationRecipientCreate,
    auth_subject: notification_recipient_auth.NotificationRecipientWrite,
    session: AsyncSession = Depends(get_db_session),
) -> NotificationRecipientSchema:
    """Create a notification recipient."""
    recipient = await notification_recipient_service.create(
        session, notification_recipient_create, auth_subject
    )
    return NotificationRecipientSchema.model_validate(recipient)


@router.get(
    "/notifications/recipients",
    response_model=PaginatedList[NotificationRecipientSchema],
    status_code=200,
    summary="Lists all notification recipients subscribed to notifications",
)
async def list(
    auth_subject: notification_recipient_auth.NotificationRecipientRead,
    pagination: PaginationParamsQuery,
    session: AsyncReadSession = Depends(get_db_read_session),
    expo_push_token: str | None = Query(None, description="Filter by Expo push token."),
    platform: NotificationRecipientPlatform | None = Query(
        None, description="Filter by platform."
    ),
) -> PaginatedList[NotificationRecipientSchema]:
    """List all devices subscribed to notifications."""
    recipients = await notification_recipient_service.list_by_user(
        session, auth_subject.subject.id, expo_push_token, platform
    )

    return PaginatedList.from_paginated_results(
        [NotificationRecipientSchema.model_validate(r) for r in recipients],
        len(recipients),
        pagination,
    )


@router.delete(
    "/notifications/recipients/{id}",
    status_code=204,
    responses={
        204: {"description": "Notification recipient unsubscribed from notifications."},
        404: {"description": "Notification recipient not found."},
    },
)
async def delete(
    id: NotificationRecipientID,
    auth_subject: notification_recipient_auth.NotificationRecipientWrite,
    session: AsyncSession = Depends(get_db_session),
) -> None:
    """Delete a notification recipient."""
    await notification_recipient_service.delete(session, auth_subject, id)


# ---------------------------------------------------------------------------
# Notification feed
# ---------------------------------------------------------------------------


@router.get("/notifications", response_model=NotificationsList)
async def get(
    auth_subject: notifications_auth.NotificationsRead,
    session: AsyncReadSession = Depends(get_db_read_session),
) -> NotificationsList:
    user_id = auth_subject.subject.id
    notifs = await notifications.get_for_user(session, user_id)
    last_read_id = await notifications.get_user_last_read(session, user_id)

    return NotificationsList(
        notifications=notifs,  # type: ignore[arg-type]  # ORM -> Pydantic coercion
        last_read_notification_id=last_read_id,
    )


@router.post("/notifications/read")
async def mark_read(
    read: NotificationsMarkRead,
    auth_subject: notifications_auth.NotificationsWrite,
    session: AsyncSession = Depends(get_db_session),
) -> None:
    await notifications.set_user_last_read(
        session, auth_subject.subject.id, read.notification_id
    )
    return None
