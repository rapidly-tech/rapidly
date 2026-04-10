"""Notification-recipient request/response models.

Defines the platform enum (iOS/Android), creation and deletion payloads,
and the full recipient schema returned by list endpoints.
"""

from enum import StrEnum

from pydantic import UUID4, Field

from rapidly.core.types import AuditableSchema, IdentifiableSchema, Schema

# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class NotificationRecipientPlatform(StrEnum):
    ios = "ios"
    android = "android"


# ---------------------------------------------------------------------------
# Mutation payloads
# ---------------------------------------------------------------------------


class NotificationRecipientCreate(Schema):
    platform: NotificationRecipientPlatform = Field(
        description="Platform of the notification recipient."
    )
    expo_push_token: str = Field(
        description="Expo push token for the notification recipient."
    )


# ---------------------------------------------------------------------------
# Read model
# ---------------------------------------------------------------------------


class NotificationRecipientSchema(IdentifiableSchema, AuditableSchema):
    id: UUID4
    user_id: UUID4 = Field(
        description="ID of the user the notification recipient belongs to."
    )
    platform: NotificationRecipientPlatform = Field(
        description="Platform of the notification recipient."
    )
    expo_push_token: str = Field(
        description="Expo push token for the notification recipient."
    )
