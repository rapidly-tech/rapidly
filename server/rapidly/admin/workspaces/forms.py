"""Admin panel workspace form schemas (Pydantic models).

Defines the admin-facing form schemas for workspace review
decisions, status transitions, threshold adjustments, and
internal-notes updates.
"""

from typing import Annotated, Literal

from annotated_types import Ge
from pydantic import (
    Discriminator,
    Field,
    StringConstraints,
    TypeAdapter,
)

from rapidly.core.types import HttpUrlToStr
from rapidly.platform.workspace.types import (
    NameInput,
    SlugInput,
    WorkspaceFeatureSettings,
)

from .. import forms

# ── Review Forms ──


class ApproveWorkspaceForm(forms.BaseForm):
    action: Annotated[Literal["approve"], forms.SkipField]
    next_review_threshold: Annotated[
        int,
        forms.CurrencyField(),
        Ge(0),
        forms.CurrencyValidator,
        Field(title="Next Review Threshold"),
    ]


class DenyWorkspaceForm(forms.BaseForm):
    action: Annotated[Literal["deny"], forms.SkipField]


class UnderReviewWorkspaceForm(forms.BaseForm):
    action: Annotated[Literal["under_review"], forms.SkipField]


class ApproveWorkspaceAppealForm(forms.BaseForm):
    action: Annotated[Literal["approve_appeal"], forms.SkipField]


class DenyWorkspaceAppealForm(forms.BaseForm):
    action: Annotated[Literal["deny_appeal"], forms.SkipField]


WorkspaceStatusForm = Annotated[
    ApproveWorkspaceForm
    | DenyWorkspaceForm
    | UnderReviewWorkspaceForm
    | ApproveWorkspaceAppealForm
    | DenyWorkspaceAppealForm,
    Discriminator("action"),
]

WorkspaceStatusFormAdapter: TypeAdapter[WorkspaceStatusForm] = TypeAdapter(
    WorkspaceStatusForm
)


# ── Workspace Forms ──


class UpdateWorkspaceBasicForm(forms.BaseForm):
    """Form for editing basic workspace settings (name, slug, invoice prefix)."""

    name: NameInput
    slug: SlugInput
    customer_invoice_prefix: Annotated[
        str,
        StringConstraints(
            to_upper=True, min_length=3, pattern=r"^[a-zA-Z0-9\-]+[a-zA-Z0-9]$"
        ),
    ]


class UpdateWorkspaceForm(forms.BaseForm):
    """Form for editing workspace settings including feature flags."""

    name: NameInput
    slug: SlugInput
    customer_invoice_prefix: Annotated[
        str,
        StringConstraints(
            to_upper=True, min_length=3, pattern=r"^[a-zA-Z0-9\-]+[a-zA-Z0-9]$"
        ),
    ]
    feature_flags: Annotated[
        WorkspaceFeatureSettings | None,
        forms.SubFormField(WorkspaceFeatureSettings),
        Field(default=None, title="Feature Flags"),
    ]


class UpdateWorkspaceDetailsDataForm(forms.BaseForm):
    about: Annotated[
        str,
        forms.TextAreaField(rows=4),
        Field(
            min_length=1,
            title="About",
            description="Brief information about you and your business",
        ),
    ]
    product_description: Annotated[
        str,
        forms.TextAreaField(rows=4),
        Field(
            min_length=1,
            title="Share Description",
            description="Description of digital products being sold",
        ),
    ]
    intended_use: Annotated[
        str,
        forms.TextAreaField(rows=3),
        Field(
            min_length=1,
            title="Intended Use",
            description="How the workspace will integrate and use Rapidly",
        ),
    ]


class UpdateWorkspaceDetailsForm(forms.BaseForm):
    website: Annotated[
        HttpUrlToStr | None,
        forms.InputField(type="url", placeholder="https://example.com"),
        Field(
            None,
            title="Website",
            description="Official website of the workspace",
        ),
    ]
    details: Annotated[UpdateWorkspaceDetailsDataForm, Field(title="Details")]


class UpdateWorkspaceInternalNotesForm(forms.BaseForm):
    internal_notes: Annotated[
        str | None,
        forms.TextAreaField(rows=10),
        Field(
            None,
            title="Internal Notes",
            description="Internal notes about this workspace (admin only)",
        ),
    ]


class UpdateWorkspaceSocialsForm(forms.BaseForm):
    """Form for editing workspace social media links."""

    youtube_url: Annotated[
        HttpUrlToStr | None,
        forms.InputField(type="url", placeholder="https://youtube.com/@channel"),
        Field(
            None,
            title="YouTube",
            description="YouTube channel URL",
        ),
    ]
    instagram_url: Annotated[
        HttpUrlToStr | None,
        forms.InputField(type="url", placeholder="https://instagram.com/username"),
        Field(
            None,
            title="Instagram",
            description="Instagram profile URL",
        ),
    ]
    linkedin_url: Annotated[
        HttpUrlToStr | None,
        forms.InputField(type="url", placeholder="https://linkedin.com/company/name"),
        Field(
            None,
            title="LinkedIn",
            description="LinkedIn profile or company page URL",
        ),
    ]
    x_url: Annotated[
        HttpUrlToStr | None,
        forms.InputField(type="url", placeholder="https://x.com/username"),
        Field(
            None,
            title="X (Twitter)",
            description="X (Twitter) profile URL",
        ),
    ]
    facebook_url: Annotated[
        HttpUrlToStr | None,
        forms.InputField(type="url", placeholder="https://facebook.com/page"),
        Field(
            None,
            title="Facebook",
            description="Facebook page URL",
        ),
    ]
    threads_url: Annotated[
        HttpUrlToStr | None,
        forms.InputField(type="url", placeholder="https://threads.net/@username"),
        Field(
            None,
            title="Threads",
            description="Threads profile URL",
        ),
    ]
    tiktok_url: Annotated[
        HttpUrlToStr | None,
        forms.InputField(type="url", placeholder="https://tiktok.com/@username"),
        Field(
            None,
            title="TikTok",
            description="TikTok profile URL",
        ),
    ]
    github_url: Annotated[
        HttpUrlToStr | None,
        forms.InputField(type="url", placeholder="https://github.com/username"),
        Field(
            None,
            title="GitHub",
            description="GitHub profile URL",
        ),
    ]
    discord_url: Annotated[
        HttpUrlToStr | None,
        forms.InputField(type="url", placeholder="https://discord.gg/invite"),
        Field(
            None,
            title="Discord",
            description="Discord server invite URL",
        ),
    ]
    other_url: Annotated[
        HttpUrlToStr | None,
        forms.InputField(type="url", placeholder="https://..."),
        Field(
            None,
            title="Other",
            description="Other social media or website URL",
        ),
    ]


# ── Account Forms ──


class DisconnectStripeAccountForm(forms.BaseForm):
    stripe_account_id: Annotated[
        str,
        StringConstraints(min_length=1),
        Field(title="Stripe Account ID"),
    ]
    reason: Annotated[
        str,
        forms.TextAreaField(rows=4),
        Field(
            min_length=1,
            title="Reason",
            description="Explain why this Stripe account is being disconnected",
        ),
    ]


class DeleteStripeAccountForm(forms.BaseForm):
    stripe_account_id: Annotated[
        str,
        StringConstraints(min_length=1),
        Field(title="Stripe Account ID"),
    ]
    reason: Annotated[
        str,
        forms.TextAreaField(rows=4),
        Field(
            min_length=1,
            title="Reason",
            description="Explain why this Stripe account is being deleted",
        ),
    ]


class AddPaymentMethodDomainForm(forms.BaseForm):
    domain_name: Annotated[
        str,
        StringConstraints(
            min_length=1,
            max_length=253,
            pattern=r"^(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)*[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?$",
        ),
        forms.InputField(type="text", placeholder="example.com"),
        Field(
            title="Domain Name",
            description="Domain to add to Apple Pay / Google Pay allowlist (e.g., example.com)",
        ),
    ]
