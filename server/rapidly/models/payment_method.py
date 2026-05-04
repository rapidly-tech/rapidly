"""Payment method model for storing saved buyer payment instruments.

A ``PaymentMethod`` represents a reusable payment instrument (e.g. a
credit card) saved on the **platform** Stripe account.  Because payment
methods are stored at the platform level rather than on individual
connected accounts, they survive workspace Stripe account changes and
can be reused across any workspace.
"""

from typing import TYPE_CHECKING, Any
from uuid import UUID

from sqlalchemy import ForeignKey, String, UniqueConstraint, Uuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, declared_attr, mapped_column, relationship

from rapidly.core.db.models import BaseEntity
from rapidly.core.extensions.sqlalchemy.types import StrEnumType
from rapidly.enums import PaymentProcessor

if TYPE_CHECKING:
    from .customer import Customer


class PaymentMethod(BaseEntity):
    """A saved payment instrument (card, bank account, etc.) on the platform."""

    __tablename__ = "payment_methods"
    __table_args__ = (UniqueConstraint("processor", "processor_id", "customer_id"),)

    processor: Mapped[PaymentProcessor] = mapped_column(
        StrEnumType(PaymentProcessor), index=True, nullable=False
    )
    processor_id: Mapped[str] = mapped_column(String, index=True, nullable=False)
    type: Mapped[str] = mapped_column(String, index=True, nullable=False)
    method_metadata: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict
    )

    customer_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("customers.id", ondelete="cascade"),
        nullable=False,
        index=True,
    )

    @declared_attr
    def customer(cls) -> Mapped["Customer"]:
        return relationship(
            "Customer",
            lazy="raise",
            back_populates="payment_methods",
            foreign_keys="[PaymentMethod.customer_id]",
        )

    @property
    def brand(self) -> str | None:
        return self.method_metadata.get("brand")

    @property
    def last4(self) -> str | None:
        return self.method_metadata.get("last4")

    @property
    def exp_month(self) -> int | None:
        return self.method_metadata.get("exp_month")

    @property
    def exp_year(self) -> int | None:
        return self.method_metadata.get("exp_year")
