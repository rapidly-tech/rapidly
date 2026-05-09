"""Public re-exports for all ORM models used across the Rapidly backend."""

from rapidly.core.db.models import AuditableModel, Model

# ── Financial ──
from .account import Account

# ── Custom fields ──
from .custom_field import CustomField

# ── Customers ──
from .customer import Customer
from .customer_session import CustomerSession
from .customer_session_code import CustomerSessionCode
from .email_verification import EmailVerification

# ── Events & webhooks ──
from .event import Event, EventClosure
from .event_type import EventType
from .external_event import ExternalEvent

# ── File sharing ──
from .file import File
from .file_share_download import FileShareDownload
from .file_share_payment import FileSharePayment, FileSharePaymentStatus
from .file_share_report import FileShareReport, FileShareReportStatus
from .file_share_session import FileShareSession, FileShareSessionStatus
from .login_code import LoginCode
from .member import Member, MemberRole
from .member_session import MemberSession

# ── Notifications ──
from .notification import Notification
from .notification_recipient import NotificationRecipient
from .oauth2_authorization_code import OAuth2AuthorizationCode

# ── OAuth2 ──
from .oauth2_client import OAuth2Client
from .oauth2_grant import OAuth2Grant
from .oauth2_token import OAuth2Token
from .payment import Payment
from .payment_method import PaymentMethod

# ── Products & pricing ──
from .share import Share, ShareVisibility
from .share_custom_field import ShareCustomField
from .share_media import ShareMedia
from .share_price import (
    SharePrice,
    SharePriceCustom,
    SharePriceFixed,
    SharePriceFree,
    SharePriceMeteredUnit,
    SharePriceSeatUnit,
)

# ── Identity & access ──
from .user import OAuthAccount, User
from .user_notification import UserNotification
from .user_session import UserSession

# ── Legacy (DB tables exist, imported for SQLAlchemy relationship resolution) ──
from .wallet import Wallet as Wallet
from .wallet_transaction import WalletTransaction as WalletTransaction

# ── Webhooks ──
from .webhook_delivery import WebhookDelivery
from .webhook_endpoint import WebhookEndpoint
from .webhook_event import WebhookEvent

# ── Workspaces ──
from .workspace import Workspace
from .workspace_access_token import WorkspaceAccessToken
from .workspace_membership import WorkspaceMembership
from .workspace_review import WorkspaceReview

__all__ = [
    "Account",
    "AuditableModel",
    "CustomField",
    "Customer",
    "CustomerSession",
    "CustomerSessionCode",
    "EmailVerification",
    "Event",
    "EventClosure",
    "EventType",
    "ExternalEvent",
    "File",
    "FileShareDownload",
    "FileSharePayment",
    "FileSharePaymentStatus",
    "FileShareReport",
    "FileShareReportStatus",
    "FileShareSession",
    "FileShareSessionStatus",
    "LoginCode",
    "Member",
    "MemberRole",
    "MemberSession",
    "Model",
    "Notification",
    "NotificationRecipient",
    "OAuth2AuthorizationCode",
    "OAuth2Client",
    "OAuth2Grant",
    "OAuth2Token",
    "OAuthAccount",
    "Payment",
    "PaymentMethod",
    "Share",
    "ShareCustomField",
    "ShareMedia",
    "SharePrice",
    "SharePriceCustom",
    "SharePriceFixed",
    "SharePriceFree",
    "SharePriceMeteredUnit",
    "SharePriceSeatUnit",
    "ShareVisibility",
    "User",
    "UserNotification",
    "UserSession",
    "WebhookDelivery",
    "WebhookEndpoint",
    "WebhookEvent",
    "Workspace",
    "WorkspaceAccessToken",
    "WorkspaceMembership",
    "WorkspaceReview",
]
