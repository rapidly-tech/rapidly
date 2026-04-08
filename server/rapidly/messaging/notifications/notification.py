"""Notification type registry and abstract base.

Defines the ``NotificationType`` enum and the ``Notification`` abstract
base class that concrete notification implementations (payment received,
review complete, etc.) must extend.
"""

from abc import abstractmethod
from datetime import datetime
from enum import StrEnum
from typing import Literal

from pydantic import UUID4, BaseModel

from rapidly.core.types import Schema
from rapidly.messaging.email.react import render_email_template


class NotificationType(StrEnum):
    workspace_create_account = (
        "MaintainerCreateAccountNotification"  # keep value for DB compat
    )
    file_share_download_completed = "FileShareDownloadCompletedNotification"
    file_share_session_expired = "FileShareSessionExpiredNotification"
    file_share_payment_received = "FileSharePaymentReceivedNotification"


class NotificationPayloadBase(BaseModel):
    @abstractmethod
    def subject(self) -> str:
        pass

    @classmethod
    @abstractmethod
    def template_name(cls) -> str:
        pass

    def render(self) -> tuple[str, str]:
        from rapidly.messaging.email.types import EmailAdapter

        return self.subject(), render_email_template(
            EmailAdapter.validate_python(
                {
                    "template": self.template_name(),
                    "props": self,
                }
            )
        )


class NotificationBase(Schema):
    id: UUID4
    created_at: datetime
    type: NotificationType


class WorkspaceCreateAccountNotificationPayload(NotificationPayloadBase):
    workspace_name: str
    url: str

    def subject(self) -> str:
        return f"Create a payout account for {self.workspace_name} now to receive funds"

    @classmethod
    def template_name(cls) -> str:
        return "notification_create_account"


class WorkspaceCreateAccountNotification(NotificationBase):
    type: Literal[NotificationType.workspace_create_account]
    payload: WorkspaceCreateAccountNotificationPayload


# ── File Sharing Notifications ──


class FileShareDownloadCompletedNotificationPayload(NotificationPayloadBase):
    file_name: str

    def subject(self) -> str:
        return f"Someone downloaded your file: {self.file_name}"

    @classmethod
    def template_name(cls) -> str:
        return "notification_file_share_download_completed"


class FileShareDownloadCompletedNotification(NotificationBase):
    type: Literal[NotificationType.file_share_download_completed]
    payload: FileShareDownloadCompletedNotificationPayload


class FileShareSessionExpiredNotificationPayload(NotificationPayloadBase):
    file_name: str

    def subject(self) -> str:
        return f"Your share link has expired: {self.file_name}"

    @classmethod
    def template_name(cls) -> str:
        return "notification_file_share_session_expired"


class FileShareSessionExpiredNotification(NotificationBase):
    type: Literal[NotificationType.file_share_session_expired]
    payload: FileShareSessionExpiredNotificationPayload


class FileSharePaymentReceivedNotificationPayload(NotificationPayloadBase):
    file_name: str
    formatted_amount: str

    def subject(self) -> str:
        return f"Payment received for {self.file_name}: {self.formatted_amount}"

    @classmethod
    def template_name(cls) -> str:
        return "notification_file_share_payment_received"


class FileSharePaymentReceivedNotification(NotificationBase):
    type: Literal[NotificationType.file_share_payment_received]
    payload: FileSharePaymentReceivedNotificationPayload


NotificationPayload = (
    WorkspaceCreateAccountNotificationPayload
    | FileShareDownloadCompletedNotificationPayload
    | FileShareSessionExpiredNotificationPayload
    | FileSharePaymentReceivedNotificationPayload
)

Notification = (
    WorkspaceCreateAccountNotification
    | FileShareDownloadCompletedNotification
    | FileShareSessionExpiredNotification
    | FileSharePaymentReceivedNotification
)
