"""Share pricing hierarchy: fixed, custom, free, metered, and seat-based.

The ``SharePrice`` base class owns the polymorphic mapping.  New-style
prices have ``type IS NULL`` (billing interval lives on the share);
legacy prices still carry a non-null ``type`` column.  The polymorphic
identity is derived at the SQL level via a ``CASE`` expression that
prefixes legacy rows with ``"legacy_"``.

Concrete leaf classes provide amount-type-specific columns and helpers.
"""

from decimal import Decimal
from enum import StrEnum
from typing import TYPE_CHECKING, Any, Literal, TypedDict
from uuid import UUID

from babel.numbers import format_decimal
from sqlalchemy import (
    Boolean,
    ColumnElement,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Uuid,
    event,
)
from sqlalchemy.dialects import postgresql
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import (
    Mapped,
    declared_attr,
    mapped_column,
    object_mapper,
    relationship,
)

from rapidly.core.currency import format_currency
from rapidly.core.db.models import BaseEntity
from rapidly.core.extensions.sqlalchemy.types import StringEnum
from rapidly.core.math import rapidly_round

if TYPE_CHECKING:
    from rapidly.models import Share


# -- Enumerations ------------------------------------------------------------


class SharePriceAmountType(StrEnum):
    """Discriminator for the amount/pricing model."""

    fixed = "fixed"
    custom = "custom"
    free = "free"
    metered_unit = "metered_unit"
    seat_based = "seat_based"


class SharePriceSource(StrEnum):
    """Where the price originated."""

    catalog = "catalog"
    ad_hoc = "ad_hoc"


# -- Seat-based tier TypedDicts ----------------------------------------------


class SeatTier(TypedDict):
    """One band in a tiered seat-pricing schedule."""

    min_seats: int
    max_seats: int | None
    price_per_seat: int


class SeatTiersData(TypedDict):
    """JSONB shape for the ``seat_tiers`` column."""

    tiers: list[SeatTier]


# -- Base price model --------------------------------------------------------


class SharePrice(BaseEntity):
    """A pricing tier attached to a share, with polymorphic subtypes."""

    __tablename__ = "share_prices"

    # -- Share association -------------------------------------------------

    share_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("shares.id", ondelete="cascade"), nullable=False, index=True
    )

    @declared_attr
    def share(cls) -> Mapped["Share"]:
        return relationship("Share", lazy="raise_on_sql", back_populates="all_prices")

    # -- Amount classification -----------------------------------------------

    amount_type: Mapped[SharePriceAmountType] = mapped_column(
        String, nullable=False, index=True
    )
    price_currency: Mapped[str] = mapped_column(
        String(3), nullable=False, use_existing_column=True
    )
    is_archived: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    source = mapped_column(
        StringEnum(SharePriceSource),
        nullable=False,
        index=True,
        default=SharePriceSource.catalog,
    )

    # -- Hybrid predicates ---------------------------------------------------

    @hybrid_property
    def is_static(self) -> bool:
        """True for price types that do not vary with consumption."""
        return self.amount_type in {
            SharePriceAmountType.fixed,
            SharePriceAmountType.free,
            SharePriceAmountType.custom,
            SharePriceAmountType.seat_based,
        }

    @is_static.inplace.expression
    @classmethod
    def _is_static_price_expression(cls) -> ColumnElement[bool]:
        return cls.amount_type.in_(
            (
                SharePriceAmountType.fixed,
                SharePriceAmountType.free,
                SharePriceAmountType.custom,
                SharePriceAmountType.seat_based,
            )
        )

    @hybrid_property
    def is_metered(self) -> bool:
        return self.amount_type in {SharePriceAmountType.metered_unit}

    @is_metered.inplace.expression
    @classmethod
    def _is_metered_price_expression(cls) -> ColumnElement[bool]:
        return cls.amount_type.in_((SharePriceAmountType.metered_unit,))

    # -- Polymorphic mapping -------------------------------------------------

    __mapper_args__ = {
        "polymorphic_on": amount_type,
    }


# -- Abstract mixins for new vs legacy prices --------------------------------


class _NewPriceMixin:
    """Shared mapper config for new-style prices (type IS NULL)."""

    __abstract__ = True

    __mapper_args__ = {
        "polymorphic_abstract": True,
        "polymorphic_load": "inline",
    }


# -- Fixed-amount price ------------------------------------------------------


class _SharePriceFixed(SharePrice):
    price_amount: Mapped[int] = mapped_column(Integer, nullable=True)
    amount_type: Mapped[Literal[SharePriceAmountType.fixed]] = mapped_column(
        use_existing_column=True, default=SharePriceAmountType.fixed
    )

    __mapper_args__ = {
        "polymorphic_abstract": True,
        "polymorphic_load": "inline",
    }


class SharePriceFixed(_NewPriceMixin, _SharePriceFixed):
    __mapper_args__ = {
        "polymorphic_identity": SharePriceAmountType.fixed,
        "polymorphic_load": "inline",
    }


# -- Custom-amount price -----------------------------------------------------


class _SharePriceCustom(SharePrice):
    amount_type: Mapped[Literal[SharePriceAmountType.custom]] = mapped_column(
        use_existing_column=True, default=SharePriceAmountType.custom
    )
    minimum_amount: Mapped[int] = mapped_column(Integer, nullable=True, default=None)
    maximum_amount: Mapped[int | None] = mapped_column(
        Integer, nullable=True, default=None
    )
    preset_amount: Mapped[int | None] = mapped_column(
        Integer, nullable=True, default=None
    )

    __mapper_args__ = {
        "polymorphic_abstract": True,
        "polymorphic_load": "inline",
    }


class SharePriceCustom(_NewPriceMixin, _SharePriceCustom):
    __mapper_args__ = {
        "polymorphic_identity": SharePriceAmountType.custom,
        "polymorphic_load": "inline",
    }


# -- Free price --------------------------------------------------------------


class _SharePriceFree(SharePrice):
    amount_type: Mapped[Literal[SharePriceAmountType.free]] = mapped_column(
        use_existing_column=True, default=SharePriceAmountType.free
    )

    __mapper_args__ = {
        "polymorphic_abstract": True,
        "polymorphic_load": "inline",
    }


class SharePriceFree(_NewPriceMixin, _SharePriceFree):
    __mapper_args__ = {
        "polymorphic_identity": SharePriceAmountType.free,
        "polymorphic_load": "inline",
    }


# -- Metered (usage-based) price ---------------------------------------------


class SharePriceMeteredUnit(SharePrice, _NewPriceMixin):
    """Per-unit consumption pricing with optional spend cap."""

    amount_type: Mapped[Literal[SharePriceAmountType.metered_unit]] = mapped_column(
        use_existing_column=True, default=SharePriceAmountType.metered_unit
    )
    unit_amount: Mapped[Decimal] = mapped_column(
        Numeric(17, 12),
        nullable=True,
    )
    cap_amount: Mapped[int | None] = mapped_column(Integer, nullable=True, default=None)
    meter_id: Mapped[UUID | None] = mapped_column(
        Uuid,
        nullable=True,
        index=True,
    )

    def get_amount_and_label(self, units: float) -> tuple[int, str]:
        """Compute the billed amount and a human-readable breakdown line."""
        label = f"({format_decimal(units, locale='en_US')} consumed units"
        label += f") \u00d7 {format_currency(self.unit_amount, self.price_currency)}"

        billable = Decimal(max(0, units))
        computed = rapidly_round(self.unit_amount * billable)

        if self.cap_amount is not None and computed > self.cap_amount:
            computed = self.cap_amount
            label += f"\u2014 Capped at {format_currency(self.cap_amount, self.price_currency)}"

        return computed, label

    __mapper_args__ = {
        "polymorphic_identity": SharePriceAmountType.metered_unit,
        "polymorphic_load": "inline",
    }


# -- Seat-based price --------------------------------------------------------


class SharePriceSeatUnit(_NewPriceMixin, SharePrice):
    """Tiered per-seat pricing with configurable seat bands."""

    amount_type: Mapped[Literal[SharePriceAmountType.seat_based]] = mapped_column(
        use_existing_column=True, default=SharePriceAmountType.seat_based
    )
    seat_tiers: Mapped[SeatTiersData] = mapped_column(
        postgresql.JSONB,
        nullable=True,
    )

    def get_tier_for_seats(self, seats: int) -> SeatTier:
        """Find the pricing tier that applies for the given seat count."""
        for tier in self.seat_tiers.get("tiers", []):
            lo = tier["min_seats"]
            hi = tier.get("max_seats")
            if seats >= lo and (hi is None or seats <= hi):
                return tier
        raise ValueError(f"No tier found for {seats} seats")

    def get_price_per_seat(self, seats: int) -> int:
        return self.get_tier_for_seats(seats)["price_per_seat"]

    def calculate_amount(self, seats: int) -> int:
        """Total charge for ``seats`` seats at the applicable tier rate."""
        return self.get_price_per_seat(seats) * seats

    def get_minimum_seats(self) -> int:
        """Lowest allowed seat count from the first tier."""
        tiers = self.seat_tiers.get("tiers", [])
        if not tiers:
            return 1
        ordered = sorted(tiers, key=lambda t: t["min_seats"])
        return ordered[0]["min_seats"]

    def get_maximum_seats(self) -> int | None:
        """Highest allowed seat count from the last tier, or None if unbounded."""
        tiers = self.seat_tiers.get("tiers", [])
        if not tiers:
            return None
        ordered = sorted(tiers, key=lambda t: t["min_seats"])
        return ordered[-1].get("max_seats")

    __mapper_args__ = {
        "polymorphic_identity": SharePriceAmountType.seat_based,
        "polymorphic_load": "inline",
    }


# -- SQLAlchemy init listener ------------------------------------------------


@event.listens_for(SharePrice, "init", propagate=True)
def set_identity(instance: SharePrice, *arg: Any, **kw: Any) -> None:
    """Resolve the polymorphic identity into the correct ``amount_type``."""
    mapper = object_mapper(instance)
    identity: str | None = mapper.polymorphic_identity

    if identity is None:
        return

    instance.amount_type = SharePriceAmountType(identity)
