"""Payout account model with Stripe Connect onboarding and fee logic.

An ``Account`` represents a creator's payment destination.  It tracks
the Stripe Connect onboarding lifecycle, per-account platform fee
overrides, billing details, and a credit balance that can offset
future payouts.
"""

from enum import StrEnum
from typing import TYPE_CHECKING, Any
from uuid import UUID

from sqlalchemy import Boolean, ForeignKey, Integer, String, Text, Uuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, declared_attr, mapped_column, relationship

from rapidly.core.address import Address, AddressType
from rapidly.core.db.models import BaseEntity
from rapidly.core.extensions.sqlalchemy import StringEnum
from rapidly.enums import AccountType

if TYPE_CHECKING:
    from .user import User
    from .workspace import Workspace

# -- Account model -----------------------------------------------------------


class Account(BaseEntity):
    """Stripe Connect payout account with onboarding and fee management."""

    class Status(StrEnum):
        """Onboarding lifecycle stages."""

        CREATED = "created"
        ONBOARDING_STARTED = "onboarding_started"
        UNDER_REVIEW = "under_review"
        DENIED = "denied"
        ACTIVE = "active"

        @property
        def display_name(self) -> str:
            return self.value.replace("_", " ").title()

        def get_display_name(self) -> str:
            return self.display_name

    __tablename__ = "accounts"

    # -- Account classification ----------------------------------------------

    account_type: Mapped[AccountType] = mapped_column(
        StringEnum(AccountType), nullable=False
    )
    status: Mapped[Status] = mapped_column(
        StringEnum(Status), nullable=False, default=Status.CREATED
    )

    # -- Admin / ownership ---------------------------------------------------

    admin_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("users.id", use_alter=True))

    @declared_attr
    def admin(cls) -> Mapped["User"]:
        return relationship("User", lazy="raise", foreign_keys="[Account.admin_id]")

    @declared_attr
    def users(cls) -> Mapped[list["User"]]:
        return relationship(
            "User",
            lazy="raise",
            back_populates="account",
            foreign_keys="[User.account_id]",
        )

    # -- Workspace associations ----------------------------------------------

    @declared_attr
    def all_workspaces(cls) -> Mapped[list["Workspace"]]:
        return relationship("Workspace", lazy="raise", back_populates="account")

    @declared_attr
    def workspaces(cls) -> Mapped[list["Workspace"]]:
        return relationship(
            "Workspace",
            lazy="raise",
            primaryjoin=(
                "and_("
                "Workspace.account_id == Account.id,"
                "Workspace.deleted_at.is_(None)"
                ")"
            ),
            viewonly=True,
        )

    # -- Stripe Connect details ----------------------------------------------

    stripe_id: Mapped[str | None] = mapped_column(
        String(100), nullable=True, default=None
    )
    open_collective_slug: Mapped[str | None] = mapped_column(
        String(255), nullable=True, default=None, deferred=True
    )

    email: Mapped[str | None] = mapped_column(String(254), nullable=True, default=None)
    country: Mapped[str] = mapped_column(String(2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3))

    is_details_submitted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    is_charges_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False)
    is_payouts_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False)

    business_type: Mapped[str | None] = mapped_column(
        String(255), nullable=True, default=None
    )

    # -- Fee configuration ---------------------------------------------------

    processor_fees_applicable: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True
    )
    _platform_fee_percent: Mapped[int | None] = mapped_column(
        Integer, name="platform_fee_percent", nullable=True, default=None
    )
    _platform_fee_fixed: Mapped[int | None] = mapped_column(
        Integer, name="platform_fee_fixed", nullable=True, default=None
    )

    # -- Review / campaign ---------------------------------------------------

    next_review_threshold: Mapped[int | None] = mapped_column(
        Integer, nullable=True, default=0
    )
    campaign_id: Mapped[UUID | None] = mapped_column(
        Uuid,
        default=None,
        index=True,
    )

    # -- Extensible data store -----------------------------------------------

    data: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)

    # -- Billing details -----------------------------------------------------

    billing_name: Mapped[str | None] = mapped_column(
        String, nullable=True, default=None
    )
    billing_address: Mapped[Address | None] = mapped_column(AddressType, nullable=True)
    billing_additional_info: Mapped[str | None] = mapped_column(
        Text, nullable=True, default=None
    )
    billing_notes: Mapped[str | None] = mapped_column(Text, nullable=True, default=None)

    # -- Credit balance ------------------------------------------------------

    credit_balance: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # -- Status predicates ---------------------------------------------------

    def is_active(self) -> bool:
        return self.status == Account.Status.ACTIVE

    def is_payout_ready(self) -> bool:
        return (
            self.is_active() and self.stripe_id is not None and self.is_payouts_enabled
        )

    def calculate_fee_in_cents(self, amount_cents: int) -> int:
        from decimal import ROUND_HALF_UP, Decimal

        from rapidly.config import settings

        percent = (
            self._platform_fee_percent
            if self._platform_fee_percent is not None
            else settings.FILE_SHARING_PLATFORM_FEE_PERCENT
        )
        fixed = self._platform_fee_fixed or 0
        fee = Decimal(amount_cents * percent) / Decimal(10_000)
        return int(fee.quantize(Decimal("1"), rounding=ROUND_HALF_UP)) + fixed
