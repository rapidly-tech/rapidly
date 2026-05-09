"""Pydantic schemas for workspace profiles, onboarding, and deletion flow."""

from datetime import datetime
from enum import StrEnum
from typing import Annotated, Any, Literal

from pydantic import (
    UUID4,
    AfterValidator,
    BeforeValidator,
    Field,
    StringConstraints,
    model_validator,
)
from pydantic.json_schema import SkipJsonSchema
from pydantic.networks import HttpUrl

from rapidly.config import settings
from rapidly.core.currency import PresentmentCurrency
from rapidly.core.email import EmailStrDNS
from rapidly.core.types import (
    WORKSPACE_ID_EXAMPLE,
    AuditableSchema,
    HttpUrlToStr,
    IdentifiableSchema,
    MergeJSONSchema,
    Schema,
    SelectorWidget,
    SlugValidator,
)
from rapidly.models.workspace import (
    WorkspaceCustomerEmailSettings,
    WorkspaceCustomerPortalSettings,
    WorkspaceNotificationSettings,
    WorkspaceStatus,
)
from rapidly.models.workspace_review import WorkspaceReview

# ── Reusable field types ──────────────────────────────────────────────

WorkspaceID = Annotated[
    UUID4,
    MergeJSONSchema({"description": "The workspace ID."}),
    SelectorWidget("/api/workspaces", "Workspace", "name"),
    Field(examples=[WORKSPACE_ID_EXAMPLE]),
]

_NAME_MIN_LENGTH: int = 3
NameInput = Annotated[str, StringConstraints(min_length=_NAME_MIN_LENGTH)]


def _reject_reserved_slug(value: str) -> str:
    if value in settings.WORKSPACE_SLUG_RESERVED_KEYWORDS:
        raise ValueError("This slug is reserved.")
    return value


SlugInput = Annotated[
    str,
    StringConstraints(to_lower=True, min_length=_NAME_MIN_LENGTH),
    SlugValidator,
    AfterValidator(_reject_reserved_slug),
]


def _discard_logo_dev_url(url: HttpUrl) -> HttpUrl | None:
    return None if (url.host and url.host.endswith("logo.dev")) else url


AvatarUrl = Annotated[HttpUrlToStr, AfterValidator(_discard_logo_dev_url)]


class WorkspaceFeatureSettings(Schema):
    member_model_enabled: bool = Field(
        False, description="If this workspace has the Member model enabled"
    )
    seat_based_pricing_enabled: bool = Field(
        False,
        description="If this workspace has seat-based pricing enabled for member sessions",
    )
    tinybird_read: bool = Field(
        False, description="If this workspace reads from Tinybird"
    )
    tinybird_compare: bool = Field(
        False,
        description="If this workspace compares Tinybird results with database",
    )


class WorkspaceDetails(Schema):
    about: str = Field(
        ..., description="Brief information about you and your business."
    )
    product_description: str = Field(
        ..., description="Description of digital products being sold."
    )
    intended_use: str = Field(
        ..., description="How the workspace will integrate and use Rapidly."
    )
    customer_acquisition: list[str] = Field(
        ..., description="Main customer acquisition channels."
    )
    future_annual_revenue: int = Field(
        ..., ge=0, description="Estimated revenue in the next 12 months"
    )
    switching: bool = Field(True, description="Switching from another platform?")
    switching_from: (
        Literal["paddle", "lemon_squeezy", "gumroad", "stripe", "other"] | None
    ) = Field(None, description="Which platform the workspace is migrating from.")
    previous_annual_revenue: int = Field(
        0, ge=0, description="Revenue from last year if applicable."
    )


# ── Social link validation ────────────────────────────────────────────


class WorkspaceSocialPlatforms(StrEnum):
    """Supported social profile platforms."""

    x = "x"
    github = "github"
    facebook = "facebook"
    instagram = "instagram"
    youtube = "youtube"
    tiktok = "tiktok"
    linkedin = "linkedin"
    other = "other"


_PLATFORM_DOMAINS: dict[str, list[str]] = {
    "x": ["twitter.com", "x.com"],
    "github": ["github.com"],
    "facebook": ["facebook.com", "fb.com"],
    "instagram": ["instagram.com"],
    "youtube": ["youtube.com", "youtu.be"],
    "tiktok": ["tiktok.com"],
    "linkedin": ["linkedin.com"],
}


class WorkspaceSocialLink(Schema):
    platform: WorkspaceSocialPlatforms = Field(
        ..., description="The social platform of the URL"
    )
    url: HttpUrlToStr = Field(..., description="The URL to the workspace profile")

    @model_validator(mode="before")
    @classmethod
    def validate_url(cls, data: dict[str, Any]) -> dict[str, Any]:
        platform = data.get("platform")
        url = data.get("url", "").lower()

        if not (platform and url) or platform == "other":
            return data

        allowed = _PLATFORM_DOMAINS.get(platform, [])
        if not any(domain in url for domain in allowed):
            raise ValueError(
                f"Invalid URL for {platform}. Must be from: {', '.join(allowed)}"
            )
        return data


class WorkspaceBase(IdentifiableSchema, AuditableSchema):
    name: str = Field(
        description="Workspace name shown in storefront, customer portal, emails etc.",
    )
    slug: str = Field(
        description="Unique workspace slug in storefront, customer portal and credit card statements.",
    )
    avatar_url: str | None = Field(
        description="Avatar URL shown in customer portal, emails etc."
    )


# ── Legacy compatibility ──────────────────────────────────────────────

_STATUS_COALESCED: dict["WorkspaceStatus", "LegacyWorkspaceStatus"] = {}


class LegacyWorkspaceStatus(StrEnum):
    """Coarsened status values kept for SDK backward compatibility."""

    CREATED = "created"
    ONBOARDING_STARTED = "onboarding_started"
    UNDER_REVIEW = "under_review"
    DENIED = "denied"
    ACTIVE = "active"

    @classmethod
    def from_status(cls, status: WorkspaceStatus) -> "LegacyWorkspaceStatus":
        return _STATUS_COALESCED[status]


# Populate after class is defined so forward refs resolve
_STATUS_COALESCED.update(
    {
        WorkspaceStatus.CREATED: LegacyWorkspaceStatus.CREATED,
        WorkspaceStatus.ONBOARDING_STARTED: LegacyWorkspaceStatus.ONBOARDING_STARTED,
        WorkspaceStatus.INITIAL_REVIEW: LegacyWorkspaceStatus.UNDER_REVIEW,
        WorkspaceStatus.ONGOING_REVIEW: LegacyWorkspaceStatus.UNDER_REVIEW,
        WorkspaceStatus.DENIED: LegacyWorkspaceStatus.DENIED,
        WorkspaceStatus.ACTIVE: LegacyWorkspaceStatus.ACTIVE,
    }
)


class WorkspacePublicBase(WorkspaceBase):
    # Attributes that we used to have publicly, but now want to hide from
    # the public schema.
    # Keep it for now for backward compatibility in the SDK
    email: SkipJsonSchema[str | None]
    website: SkipJsonSchema[str | None]
    socials: SkipJsonSchema[list[WorkspaceSocialLink]]
    status: Annotated[
        SkipJsonSchema[LegacyWorkspaceStatus],
        BeforeValidator(LegacyWorkspaceStatus.from_status),
    ]
    details_submitted_at: SkipJsonSchema[datetime | None]

    feature_settings: SkipJsonSchema[WorkspaceFeatureSettings | None]
    notification_settings: SkipJsonSchema[WorkspaceNotificationSettings]
    customer_email_settings: SkipJsonSchema[WorkspaceCustomerEmailSettings]


class Workspace(WorkspaceBase):
    email: str | None = Field(description="Public support email.")
    website: str | None = Field(description="Official website of the workspace.")
    socials: list[WorkspaceSocialLink] = Field(
        description="Links to social profiles.",
    )
    status: WorkspaceStatus = Field(description="Current workspace status")
    details_submitted_at: datetime | None = Field(
        description="When the business details were submitted.",
    )

    default_presentment_currency: PresentmentCurrency = Field(
        description=(
            "Default presentment currency. "
            "Used as fallback in storefront and customer portal, "
            "if the customer's local currency is not available."
        )
    )

    feature_settings: WorkspaceFeatureSettings | None = Field(
        description="Workspace feature settings",
    )
    notification_settings: WorkspaceNotificationSettings = Field(
        description="Settings related to notifications",
    )
    customer_email_settings: WorkspaceCustomerEmailSettings = Field(
        description="Settings related to customer emails",
    )
    customer_portal_settings: WorkspaceCustomerPortalSettings = Field(
        description="Settings related to the customer portal",
    )


class WorkspaceCreate(Schema):
    name: NameInput
    slug: SlugInput
    avatar_url: AvatarUrl | None = None
    email: EmailStrDNS | None = Field(None, description="Public support email.")
    website: HttpUrlToStr | None = Field(
        None, description="Official website of the workspace."
    )
    socials: list[WorkspaceSocialLink] | None = Field(
        None,
        description="Link to social profiles.",
    )
    details: WorkspaceDetails | None = Field(
        None,
        description="Additional, private, business details Rapidly needs about active workspaces for compliance (KYC).",
    )
    feature_settings: WorkspaceFeatureSettings | None = None
    notification_settings: WorkspaceNotificationSettings | None = None
    customer_email_settings: WorkspaceCustomerEmailSettings | None = None
    customer_portal_settings: WorkspaceCustomerPortalSettings | None = None
    default_presentment_currency: PresentmentCurrency = Field(
        PresentmentCurrency.usd,
        description="Default presentment currency for the workspace",
    )


class WorkspaceUpdate(Schema):
    name: NameInput | None = None
    avatar_url: AvatarUrl | None = None

    email: EmailStrDNS | None = Field(None, description="Public support email.")
    website: HttpUrlToStr | None = Field(
        None, description="Official website of the workspace."
    )
    socials: list[WorkspaceSocialLink] | None = Field(
        None, description="Links to social profiles."
    )
    details: WorkspaceDetails | None = Field(
        None,
        description="Additional, private, business details Rapidly needs about active workspaces for compliance (KYC).",
    )

    default_presentment_currency: PresentmentCurrency | None = Field(
        None,
        description="Default presentment currency for the workspace",
    )

    feature_settings: WorkspaceFeatureSettings | None = None
    notification_settings: WorkspaceNotificationSettings | None = None
    customer_email_settings: WorkspaceCustomerEmailSettings | None = None
    customer_portal_settings: WorkspaceCustomerPortalSettings | None = None


class WorkspacePaymentStep(Schema):
    id: str = Field(description="Step identifier")
    title: str = Field(description="Step title")
    description: str = Field(description="Step description")
    completed: bool = Field(description="Whether the step is completed")


class WorkspacePaymentStatus(Schema):
    payment_ready: bool = Field(
        description="Whether the workspace is ready to accept payments"
    )
    steps: list[WorkspacePaymentStep] = Field(description="List of onboarding steps")
    workspace_status: WorkspaceStatus = Field(description="Current workspace status")


class WorkspaceAppealRequest(Schema):
    reason: Annotated[
        str,
        StringConstraints(min_length=50, max_length=5000),
        Field(
            description="Detailed explanation of why this workspace should be approved. Minimum 50 characters."
        ),
    ]


class WorkspaceAppealResponse(Schema):
    success: bool = Field(description="Whether the appeal was successfully submitted")
    message: str = Field(description="Success or error message")
    appeal_submitted_at: datetime | None = Field(
        default=None, description="When the appeal was submitted"
    )


class WorkspaceReviewStatus(Schema):
    verdict: str | None = Field(
        default=None, description="AI validation verdict (PASS, FAIL, or UNCERTAIN)"
    )
    reason: str | None = Field(default=None, description="Reason for the verdict")
    appeal_submitted_at: datetime | None = Field(
        default=None, description="When appeal was submitted"
    )
    appeal_reason: str | None = Field(default=None, description="Reason for the appeal")
    appeal_decision: WorkspaceReview.AppealDecision | None = Field(
        default=None, description="Decision on the appeal (approved/rejected)"
    )
    appeal_reviewed_at: datetime | None = Field(
        default=None, description="When appeal was reviewed"
    )


class WorkspaceDeletionBlockedReason(StrEnum):
    """Reasons why an workspace cannot be immediately deleted."""

    STRIPE_ACCOUNT_DELETION_FAILED = "stripe_account_deletion_failed"


class WorkspaceDeletionResponse(Schema):
    """Response for workspace deletion request."""

    deleted: bool = Field(description="Whether the workspace was immediately deleted")
    requires_support: bool = Field(
        description="Whether a support ticket was created for manual handling"
    )
    blocked_reasons: list[WorkspaceDeletionBlockedReason] = Field(
        default_factory=list,
        description="Reasons why immediate deletion is blocked",
    )
