"""Workspace model with onboarding lifecycle, feature flags, and settings.

An ``Workspace`` is the tenant boundary: it owns products, customers,
webhook endpoints, and payout accounts.  Settings (notification preferences,
customer emails, portal behaviour) are stored as JSONB columns with typed
defaults.
"""

from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING, Any, Self, TypedDict
from urllib.parse import urlparse
from uuid import UUID

from sqlalchemy import (
    TIMESTAMP,
    CheckConstraint,
    ColumnElement,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    and_,
)
from sqlalchemy.dialects.postgresql import CITEXT, JSONB
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import Mapped, declared_attr, mapped_column, relationship

from rapidly.config import settings
from rapidly.core.currency import PresentmentCurrency
from rapidly.core.db.models import BaseEntity, RateLimitMixin
from rapidly.core.extensions.sqlalchemy import StringEnum

from .account import Account

if TYPE_CHECKING:
    from rapidly.messaging.email.sender import EmailFromReply

    from .share import Share
    from .workspace_review import WorkspaceReview

# Logo resolution service image size.
_LOGO_SIZE: int = 64

# ── Settings TypedDicts ────────────────────────────────────────────────


class WorkspaceSocials(TypedDict):
    """A single social-media link entry."""

    platform: str
    url: str


class WorkspaceDetails(TypedDict):
    """Onboarding questionnaire payload."""

    about: str
    product_description: str
    intended_use: str
    customer_acquisition: list[str]
    future_annual_revenue: int
    switching: bool
    switching_from: str | None
    previous_annual_revenue: int


class WorkspaceNotificationSettings(TypedDict):
    """Which internal notifications the workspace admin receives."""

    new_payment: bool


_default_notification_settings: WorkspaceNotificationSettings = {
    "new_payment": True,
}


class WorkspaceCustomerEmailSettings(TypedDict):
    """Which transactional emails are sent to the org's customers."""

    payment_confirmation: bool


_default_customer_email_settings: WorkspaceCustomerEmailSettings = {
    "payment_confirmation": True,
}


class CustomerPortalUsageSettings(TypedDict):
    """Visibility toggle for usage data in the customer portal."""

    show: bool


class WorkspaceCustomerPortalSettings(TypedDict):
    """Customer-portal UI toggles."""

    usage: CustomerPortalUsageSettings


_default_customer_portal_settings: WorkspaceCustomerPortalSettings = {
    "usage": {"show": True},
}


# ── Onboarding status enum ────────────────────────────────────────────


class WorkspaceStatus(StrEnum):
    """Onboarding / review lifecycle stages."""

    CREATED = "created"
    ONBOARDING_STARTED = "onboarding_started"
    INITIAL_REVIEW = "initial_review"
    ONGOING_REVIEW = "ongoing_review"
    DENIED = "denied"
    ACTIVE = "active"

    @property
    def display_name(self) -> str:
        return self.value.replace("_", " ").title()

    # Keep old method for backwards compatibility.
    def get_display_name(self) -> str:
        return self.display_name

    @classmethod
    def review_statuses(cls) -> set[Self]:
        return {cls.INITIAL_REVIEW, cls.ONGOING_REVIEW}  # pyright: ignore

    @classmethod
    def payment_ready_statuses(cls) -> set[Self]:
        return {cls.ACTIVE, *cls.review_statuses()}  # pyright: ignore


# ── Workspace model ─────────────────────────────────────────────────


class Workspace(RateLimitMixin, BaseEntity):
    """Tenant entity that owns products, customers, and payout accounts."""

    __tablename__ = "workspaces"
    __table_args__ = (
        UniqueConstraint("slug"),
        CheckConstraint(
            "next_review_threshold >= 0", name="next_review_threshold_positive"
        ),
    )

    name: Mapped[str] = mapped_column(String, nullable=False, index=True)
    slug: Mapped[str] = mapped_column(CITEXT, nullable=False, unique=True)
    _avatar_url: Mapped[str | None] = mapped_column(
        String, name="avatar_url", nullable=True
    )

    email: Mapped[str | None] = mapped_column(String, nullable=True, default=None)
    website: Mapped[str | None] = mapped_column(String, nullable=True, default=None)

    @property
    def avatar_url(self) -> str | None:
        if self._avatar_url:
            return self._avatar_url

        if not self.website or not settings.LOGO_DEV_PUBLISHABLE_KEY:
            return None

        parsed = urlparse(self.website)
        domain = parsed.netloc or parsed.path
        domain = domain.lower().removeprefix("www.")

        return f"https://img.logo.dev/{domain}?size={_LOGO_SIZE}&retina=true&token={settings.LOGO_DEV_PUBLISHABLE_KEY}&fallback=404"

    @avatar_url.setter
    def avatar_url(self, value: str | None) -> None:
        self._avatar_url = value

    socials: Mapped[list[WorkspaceSocials]] = mapped_column(
        JSONB, nullable=False, default=list
    )
    details: Mapped[WorkspaceDetails] = mapped_column(
        JSONB, nullable=False, default=dict
    )
    details_submitted_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True)
    )

    customer_invoice_prefix: Mapped[str] = mapped_column(String, nullable=False)
    customer_invoice_next_number: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1
    )

    account_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("accounts.id", ondelete="set null"), nullable=True
    )
    status: Mapped[WorkspaceStatus] = mapped_column(
        StringEnum(WorkspaceStatus),
        nullable=False,
        default=WorkspaceStatus.CREATED,
    )
    next_review_threshold: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )
    status_updated_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )
    initially_reviewed_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )

    internal_notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    @declared_attr
    def account(cls) -> Mapped[Account | None]:
        return relationship(Account, lazy="raise", back_populates="workspaces")

    onboarded_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    ai_onboarding_completed_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True, default=None
    )

    # Timestamp when the workspace was suspended from all platform activity.
    blocked_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=True,
        default=None,
    )

    profile_settings: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict
    )

    notification_settings: Mapped[WorkspaceNotificationSettings] = mapped_column(
        JSONB, nullable=False, default=_default_notification_settings
    )

    customer_email_settings: Mapped[WorkspaceCustomerEmailSettings] = mapped_column(
        JSONB, nullable=False, default=_default_customer_email_settings
    )

    customer_portal_settings: Mapped[WorkspaceCustomerPortalSettings] = mapped_column(
        JSONB, nullable=False, default=_default_customer_portal_settings
    )

    #
    # Feature Flags
    #

    feature_settings: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict
    )

    #
    # Currency settings
    #
    default_presentment_currency: Mapped[PresentmentCurrency] = mapped_column(
        String(3), nullable=False, default="usd"
    )

    #
    # Fields synced from GitHub
    #

    # Free-text description shown on the workspace's public profile.
    bio: Mapped[str | None] = mapped_column(String, nullable=True, default=None)
    company: Mapped[str | None] = mapped_column(String, nullable=True, default=None)
    blog: Mapped[str | None] = mapped_column(String, nullable=True, default=None)
    location: Mapped[str | None] = mapped_column(String, nullable=True, default=None)
    twitter_username: Mapped[str | None] = mapped_column(
        String, nullable=True, default=None
    )

    #
    # ── End of GitHub-synced fields ──
    #

    @hybrid_property
    def can_authenticate(self) -> bool:
        return self.deleted_at is None and self.blocked_at is None

    @can_authenticate.inplace.expression
    @classmethod
    def _can_authenticate_expression(cls) -> ColumnElement[bool]:
        return and_(cls.deleted_at.is_(None), cls.blocked_at.is_(None))

    @hybrid_property
    def storefront_enabled(self) -> bool:
        return self.profile_settings.get("enabled", False)

    @storefront_enabled.inplace.expression
    @classmethod
    def _storefront_enabled_expression(cls) -> ColumnElement[bool]:
        return Workspace.profile_settings["enabled"].as_boolean()

    @hybrid_property
    def is_under_review(self) -> bool:
        return self.status in WorkspaceStatus.review_statuses()

    @is_under_review.inplace.expression
    @classmethod
    def _is_under_review_expression(cls) -> ColumnElement[bool]:
        return cls.status.in_(WorkspaceStatus.review_statuses())

    @declared_attr
    def all_shares(cls) -> Mapped[list["Share"]]:
        return relationship("Share", lazy="raise", back_populates="workspace")

    @declared_attr
    def shares(cls) -> Mapped[list["Share"]]:
        return relationship(
            "Share",
            lazy="raise",
            primaryjoin=(
                "and_(Share.workspace_id == Workspace.id, Share.is_archived.is_(False))"
            ),
            viewonly=True,
        )

    @declared_attr
    def review(cls) -> Mapped["WorkspaceReview | None"]:
        return relationship(
            "WorkspaceReview",
            lazy="raise",
            back_populates="workspace",
            cascade="delete, delete-orphan",
            uselist=False,  # This makes it a one-to-one relationship
        )

    def is_blocked(self) -> bool:
        return self.blocked_at is not None

    def is_active(self) -> bool:
        return self.status == WorkspaceStatus.ACTIVE

    @property
    def email_from_reply(self) -> "EmailFromReply":
        return {
            "from_name": f"{self.name} (via {settings.EMAIL_FROM_NAME})",
            "reply_to_name": self.name,
            "reply_to_email_addr": self.email
            or settings.EMAIL_DEFAULT_REPLY_TO_EMAIL_ADDRESS,
        }
