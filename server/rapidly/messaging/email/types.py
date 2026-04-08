"""Typed email template definitions and their props schemas.

Each email template is represented as a ``(StrEnum, TypedDict)`` pair:
the enum variant selects the React-Email template file, and the
TypedDict describes the props passed into the renderer.
"""

import json
import sys
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import BaseModel, Discriminator, TypeAdapter

from rapidly.messaging.notifications.notification import (
    FileShareDownloadCompletedNotificationPayload,
    FileSharePaymentReceivedNotificationPayload,
    FileShareSessionExpiredNotificationPayload,
    WorkspaceCreateAccountNotificationPayload,
)
from rapidly.platform.workspace.types import Workspace

# ── Base Email ──


class EmailTemplate(StrEnum):
    login_code = "login_code"
    customer_session_code = "customer_session_code"
    email_update = "email_update"
    oauth2_leaked_client = "oauth2_leaked_client"
    oauth2_leaked_token = "oauth2_leaked_token"
    workspace_access_token_leaked = "organization_access_token_leaked"
    workspace_invite = "organization_invite"
    workspace_account_unlink = "organization_account_unlink"
    workspace_under_review = "organization_under_review"
    workspace_reviewed = "organization_reviewed"
    webhook_endpoint_disabled = "webhook_endpoint_disabled"
    notification_create_account = "notification_create_account"
    notification_file_share_download_completed = (
        "notification_file_share_download_completed"
    )
    notification_file_share_session_expired = "notification_file_share_session_expired"
    notification_file_share_payment_received = (
        "notification_file_share_payment_received"
    )


class EmailProps(BaseModel):
    email: str


# ── Authentication Emails ──


class LoginCodeProps(EmailProps):
    code: str
    code_lifetime_minutes: int


class LoginCodeEmail(BaseModel):
    template: Literal[EmailTemplate.login_code] = EmailTemplate.login_code
    props: LoginCodeProps


class CustomerSessionCodeProps(EmailProps):
    workspace: Workspace
    code: str
    code_lifetime_minutes: int
    url: str


class CustomerSessionCodeEmail(BaseModel):
    template: Literal[EmailTemplate.customer_session_code] = (
        EmailTemplate.customer_session_code
    )
    props: CustomerSessionCodeProps


# ── Account Management Emails ──


class EmailUpdateProps(EmailProps):
    token_lifetime_minutes: int
    url: str


class EmailUpdateEmail(BaseModel):
    template: Literal[EmailTemplate.email_update] = EmailTemplate.email_update
    props: EmailUpdateProps


# ── Security Alert Emails ──


class OAuth2LeakedClientProps(EmailProps):
    token_type: str
    client_name: str
    notifier: str
    url: str


class OAuth2LeakedClientEmail(BaseModel):
    template: Literal[EmailTemplate.oauth2_leaked_client] = (
        EmailTemplate.oauth2_leaked_client
    )
    props: OAuth2LeakedClientProps


class OAuth2LeakedTokenProps(EmailProps):
    client_name: str
    notifier: str
    url: str


class OAuth2LeakedTokenEmail(BaseModel):
    template: Literal[EmailTemplate.oauth2_leaked_token] = (
        EmailTemplate.oauth2_leaked_token
    )
    props: OAuth2LeakedTokenProps


class WorkspaceAccessTokenLeakedProps(EmailProps):
    workspace_access_token: str
    notifier: str
    url: str


class WorkspaceAccessTokenLeakedEmail(BaseModel):
    template: Literal[EmailTemplate.workspace_access_token_leaked] = (
        EmailTemplate.workspace_access_token_leaked
    )
    props: WorkspaceAccessTokenLeakedProps


# ── Workspace Emails ──


class WorkspaceInviteProps(EmailProps):
    workspace_name: str
    inviter_email: str
    invite_url: str


class WorkspaceInviteEmail(BaseModel):
    template: Literal[EmailTemplate.workspace_invite] = EmailTemplate.workspace_invite
    props: WorkspaceInviteProps


class WorkspaceUnderReviewProps(EmailProps):
    workspace: Workspace


class WorkspaceUnderReviewEmail(BaseModel):
    template: Literal[EmailTemplate.workspace_under_review] = (
        EmailTemplate.workspace_under_review
    )
    props: WorkspaceUnderReviewProps


class WorkspaceReviewedProps(EmailProps):
    workspace: Workspace


class WorkspaceReviewedEmail(BaseModel):
    template: Literal[EmailTemplate.workspace_reviewed] = (
        EmailTemplate.workspace_reviewed
    )
    props: WorkspaceReviewedProps


# ── Webhook & Notification Emails ──


class WebhookEndpointDisabledProps(EmailProps):
    workspace: Workspace
    webhook_endpoint_url: str
    dashboard_url: str


class WebhookEndpointDisabledEmail(BaseModel):
    template: Literal[EmailTemplate.webhook_endpoint_disabled] = (
        EmailTemplate.webhook_endpoint_disabled
    )
    props: WebhookEndpointDisabledProps


class NotificationCreateAccountEmail(BaseModel):
    template: Literal[EmailTemplate.notification_create_account] = (
        EmailTemplate.notification_create_account
    )
    props: WorkspaceCreateAccountNotificationPayload


class WorkspaceAccountUnlinkProps(EmailProps):
    workspace_kept_name: str
    workspaces_unlinked: list[str]


class WorkspaceAccountUnlinkEmail(BaseModel):
    template: Literal[EmailTemplate.workspace_account_unlink] = (
        EmailTemplate.workspace_account_unlink
    )
    props: WorkspaceAccountUnlinkProps


# ── File Sharing Notification Emails ──


class NotificationFileShareDownloadCompletedEmail(BaseModel):
    template: Literal[EmailTemplate.notification_file_share_download_completed] = (
        EmailTemplate.notification_file_share_download_completed
    )
    props: FileShareDownloadCompletedNotificationPayload


class NotificationFileShareSessionExpiredEmail(BaseModel):
    template: Literal[EmailTemplate.notification_file_share_session_expired] = (
        EmailTemplate.notification_file_share_session_expired
    )
    props: FileShareSessionExpiredNotificationPayload


class NotificationFileSharePaymentReceivedEmail(BaseModel):
    template: Literal[EmailTemplate.notification_file_share_payment_received] = (
        EmailTemplate.notification_file_share_payment_received
    )
    props: FileSharePaymentReceivedNotificationPayload


# ── Discriminated Union ──

Email = Annotated[
    LoginCodeEmail
    | CustomerSessionCodeEmail
    | EmailUpdateEmail
    | OAuth2LeakedClientEmail
    | OAuth2LeakedTokenEmail
    | WorkspaceAccessTokenLeakedEmail
    | WorkspaceInviteEmail
    | WorkspaceAccountUnlinkEmail
    | WorkspaceUnderReviewEmail
    | WorkspaceReviewedEmail
    | WebhookEndpointDisabledEmail
    | NotificationCreateAccountEmail
    | NotificationFileShareDownloadCompletedEmail
    | NotificationFileShareSessionExpiredEmail
    | NotificationFileSharePaymentReceivedEmail,
    Discriminator("template"),
]

EmailAdapter: TypeAdapter[Email] = TypeAdapter(Email)


if __name__ == "__main__":
    openapi_schema = {
        "openapi": "3.1.0",
        "paths": {},
        "components": {
            "schemas": EmailAdapter.json_schema(
                mode="serialization", ref_template="#/components/schemas/{model}"
            )["$defs"]
        },
    }
    sys.stdout.write(json.dumps(openapi_schema, indent=2))
