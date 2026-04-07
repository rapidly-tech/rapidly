"""Pydantic schemas for share catalogue: prices, variants, and media attachments."""

import builtins
from typing import Annotated, Literal

from pydantic import (
    UUID4,
    Discriminator,
    Field,
    field_validator,
)

from rapidly.catalog.custom_field.types import (
    AttachedCustomField,
    AttachedCustomFieldListCreate,
)
from rapidly.catalog.file.types import ShareMediaFileRead
from rapidly.core.currency import PresentmentCurrency
from rapidly.core.db.models import Model
from rapidly.core.metadata import (
    MetadataInputMixin,
    MetadataOutputMixin,
)
from rapidly.core.types import (
    AuditableSchema,
    EmptyStrToNoneValidator,
    IdentifiableSchema,
    MergeJSONSchema,
    Schema,
    SelectorWidget,
    SetSchemaReference,
)
from rapidly.models.share import ShareVisibility
from rapidly.models.share_price import (
    SharePriceAmountType,
    SharePriceSource,
)
from rapidly.models.share_price import (
    SharePriceCustom as SharePriceCustomModel,
)
from rapidly.models.share_price import (
    SharePriceFixed as SharePriceFixedModel,
)
from rapidly.models.share_price import (
    SharePriceFree as SharePriceFreeModel,
)
from rapidly.platform.workspace.types import WorkspaceID

# ── Constants ─────────────────────────────────────────────────────────

SHARE_NAME_MIN_LENGTH: int = 3
INT_MAX_VALUE: int = 2_147_483_647  # PostgreSQL int4 range limit

ShareID = Annotated[
    UUID4,
    MergeJSONSchema({"description": "The share ID."}),
    SelectorWidget("/api/shares", "Share", "name"),
]

# Stripe payment-intent amount bounds
MAXIMUM_PRICE_AMOUNT: int = 99_999_999
MINIMUM_PRICE_AMOUNT: int = 50


PriceAmount = Annotated[
    int,
    Field(
        ...,
        ge=MINIMUM_PRICE_AMOUNT,
        le=MAXIMUM_PRICE_AMOUNT,
        description="The price in cents.",
    ),
]
PriceCurrency = Annotated[
    PresentmentCurrency,
    Field(description="The currency in which the customer will be charged."),
]
ShareName = Annotated[
    str,
    Field(
        min_length=SHARE_NAME_MIN_LENGTH,
        description="The name of the share.",
    ),
]
ShareDescription = Annotated[
    str | None,
    Field(description="The description of the share."),
    EmptyStrToNoneValidator,
]


# ── Price creation schemas ────────────────────────────────────────────


class SharePriceCreateBase(Schema):
    """Base for all price-creation discriminated variants."""

    amount_type: SharePriceAmountType
    price_currency: PriceCurrency = PresentmentCurrency.usd

    def get_model_class(self) -> builtins.type[Model]:
        raise NotImplementedError()


class SharePriceFixedCreate(SharePriceCreateBase):
    """
    Schema to create a fixed price.
    """

    amount_type: Literal[SharePriceAmountType.fixed]
    price_amount: PriceAmount

    def get_model_class(self) -> builtins.type[SharePriceFixedModel]:
        return SharePriceFixedModel


class SharePriceCustomCreate(SharePriceCreateBase):
    """
    Schema to create a pay-what-you-want price.
    """

    amount_type: Literal[SharePriceAmountType.custom]
    minimum_amount: int = Field(
        default=MINIMUM_PRICE_AMOUNT,
        ge=0,
        description=(
            "The minimum amount the customer can pay. "
            "If set to 0, the price is 'free or pay what you want' and $0 is accepted. "
            "If set to a value between 1-49, it will be rejected. "
            "Defaults to 50 cents."
        ),
    )
    maximum_amount: PriceAmount | None = Field(
        default=None,
        le=1_000_000,  # $10K
        description="The maximum amount the customer can pay.",
    )
    preset_amount: PriceAmount | None = Field(
        default=None,
        ge=0,
        le=1_000_000,  # $10K
        description=(
            "The initial amount shown to the customer. "
            "If 0, the customer will see $0 as the default. "
            "Values between 1-49 are rejected."
        ),
    )

    @field_validator("minimum_amount", "preset_amount")
    @classmethod
    def validate_amount_not_in_minimum_gap(cls, v: int | None) -> int | None:
        # Minimum payment is $0.50, so values 1-49 are invalid
        # 0 is valid (free), None is valid (use default), >= 50 is valid
        if v is not None and 0 < v < MINIMUM_PRICE_AMOUNT:
            raise ValueError(
                f"Amount must be 0 (for free) or at least {MINIMUM_PRICE_AMOUNT} cents"
            )
        return v

    def get_model_class(self) -> builtins.type[SharePriceCustomModel]:
        return SharePriceCustomModel


class SharePriceFreeCreate(SharePriceCreateBase):
    """
    Schema to create a free price.
    """

    amount_type: Literal[SharePriceAmountType.free]

    def get_model_class(self) -> builtins.type[SharePriceFreeModel]:
        return SharePriceFreeModel


SharePriceCreate = Annotated[
    SharePriceFixedCreate | SharePriceCustomCreate | SharePriceFreeCreate,
    Discriminator("amount_type"),
]


SharePriceCreateList = Annotated[
    list[SharePriceCreate],
    Field(min_length=1),
    MergeJSONSchema(
        {
            "title": "SharePriceCreateList",
            "description": (
                "List of prices for the share. "
                "At most one static price (fixed, custom or free) is allowed."
            ),
        }
    ),
]


class ShareCreateBase(MetadataInputMixin, Schema):
    name: ShareName
    description: ShareDescription = None
    visibility: ShareVisibility = Field(
        default=ShareVisibility.public,
        description="The visibility of the share.",
    )
    prices: SharePriceCreateList = Field(
        ...,
        description="List of available prices for this share. "
        "It should contain at most one static price (fixed, custom or free).",
    )
    medias: list[UUID4] | None = Field(
        default=None,
        description=(
            "List of file IDs. "
            "Each one must be on the same workspace as the share, "
            "of type `product_media` and correctly uploaded."
        ),
    )
    attached_custom_fields: AttachedCustomFieldListCreate = Field(default_factory=list)
    workspace_id: WorkspaceID | None = Field(
        default=None,
        description=(
            "The ID of the workspace owning the share. "
            "**Required unless you use an workspace token.**"
        ),
    )


class ShareCreate(ShareCreateBase):
    """Schema for creating a share (one-time purchase)."""

    pass


class ExistingSharePrice(Schema):
    """
    A price that already exists for this share.

    Useful when updating a share if you want to keep an existing price.
    """

    id: UUID4


SharePriceUpdate = Annotated[
    ExistingSharePrice | SharePriceCreate, Field(union_mode="left_to_right")
]


class ShareUpdate(MetadataInputMixin, Schema):
    """
    Schema to update a share.
    """

    name: ShareName | None = None
    description: ShareDescription = None
    is_archived: bool | None = Field(
        default=None,
        description=(
            "Whether the share is archived. "
            "If `true`, the share won't be available for purchase anymore."
        ),
    )
    visibility: ShareVisibility | None = Field(
        default=None,
        description="The visibility of the share.",
    )
    prices: list[SharePriceUpdate] | None = Field(
        default=None,
        description=(
            "List of available prices for this share. "
            "If you want to keep existing prices, include them in the list "
            "as an `ExistingSharePrice` object."
        ),
    )
    medias: list[UUID4] | None = Field(
        default=None,
        description=(
            "List of file IDs. "
            "Each one must be on the same workspace as the share, "
            "of type `product_media` and correctly uploaded."
        ),
    )
    attached_custom_fields: AttachedCustomFieldListCreate | None = None


class SharePriceBase(AuditableSchema):
    id: UUID4 = Field(description="The ID of the price.")
    source: SharePriceSource = Field(
        description=(
            "The source of the price. "
            "`catalog` is a predefined price, "
            "while `ad_hoc` is a price created dynamically during the payment flow."
        )
    )
    amount_type: SharePriceAmountType = Field(
        description="The type of amount, either fixed or custom."
    )
    price_currency: PriceCurrency
    is_archived: bool = Field(
        description="Whether the price is archived and no longer available."
    )
    share_id: UUID4 = Field(description="The ID of the share owning the price.")


class SharePriceFixedBase(SharePriceBase):
    amount_type: Literal[SharePriceAmountType.fixed]
    price_amount: int = Field(description="The price in cents.")


class SharePriceCustomBase(SharePriceBase):
    amount_type: Literal[SharePriceAmountType.custom]
    minimum_amount: int = Field(
        description=(
            "The minimum amount the customer can pay. "
            "If 0, the price is 'free or pay what you want'. "
            "Defaults to 50 cents."
        )
    )
    maximum_amount: int | None = Field(
        description="The maximum amount the customer can pay."
    )
    preset_amount: int | None = Field(
        description="The initial amount shown to the customer."
    )

    @field_validator("minimum_amount", mode="before")
    @classmethod
    def set_minimum_amount_default(cls, v: int | None) -> int:
        return v if v is not None else MINIMUM_PRICE_AMOUNT


class SharePriceFreeBase(SharePriceBase):
    amount_type: Literal[SharePriceAmountType.free]


class SharePriceFixed(SharePriceFixedBase):
    """
    A fixed price for a share.
    """


class SharePriceCustom(SharePriceCustomBase):
    """
    A pay-what-you-want price for a share.
    """


class SharePriceFree(SharePriceFreeBase):
    """
    A free price for a share.
    """


SharePrice = Annotated[
    SharePriceFixed | SharePriceCustom | SharePriceFree,
    Discriminator("amount_type"),
    SetSchemaReference("SharePrice"),
]


# ── Read schemas ──────────────────────────────────────────────────────


class ShareBase(AuditableSchema, IdentifiableSchema):
    """Shared fields across share read responses."""

    name: str = Field(description="The name of the share.")
    description: str | None = Field(description="The description of the share.")
    visibility: ShareVisibility = Field(description="The visibility of the share.")
    is_archived: bool = Field(
        description="Whether the share is archived and no longer available."
    )
    workspace_id: UUID4 = Field(description="The ID of the workspace owning the share.")


SharePriceList = Annotated[
    list[SharePrice],
    Field(
        description="List of prices for this share.",
    ),
]
ShareMediaList = Annotated[
    list[ShareMediaFileRead],
    Field(
        description="List of medias associated to the share.",
    ),
]


class Share(MetadataOutputMixin, ShareBase):
    """
    A share.
    """

    prices: SharePriceList
    medias: ShareMediaList
    attached_custom_fields: list[AttachedCustomField] = Field(
        description="List of custom fields attached to the share."
    )
