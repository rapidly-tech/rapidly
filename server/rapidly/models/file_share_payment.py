"""ORM model for payments attached to file sharing sessions."""

from enum import StrEnum
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import ForeignKey, Index, Integer, String, Uuid
from sqlalchemy.orm import Mapped, declared_attr, mapped_column, relationship

from rapidly.core.db.models.base import BaseEntity
from rapidly.core.extensions.sqlalchemy.types import StringEnum

if TYPE_CHECKING:
    from .customer import Customer
    from .file_share_session import FileShareSession
    from .payment import Payment


class FileSharePaymentStatus(StrEnum):
    pending = "pending"
    completed = "completed"
    refunded = "refunded"
    failed = "failed"


class FileSharePayment(BaseEntity):
    """Tracks a Stripe payment for a paid file download."""

    __tablename__ = "file_share_payments"
    __table_args__ = (
        Index(
            "ix_file_share_payments_stripe_checkout_session_id",
            "stripe_checkout_session_id",
            unique=True,
            postgresql_where="stripe_checkout_session_id IS NOT NULL",
        ),
    )

    session_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("file_share_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    status: Mapped[FileSharePaymentStatus] = mapped_column(
        StringEnum(FileSharePaymentStatus),
        nullable=False,
        default=FileSharePaymentStatus.pending,
    )
    amount_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="usd")
    platform_fee_cents: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    stripe_checkout_session_id: Mapped[str | None] = mapped_column(
        String(255), nullable=True
    )
    stripe_payment_intent_id: Mapped[str | None] = mapped_column(
        String(255), nullable=True
    )
    buyer_ip_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    buyer_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    buyer_name: Mapped[str | None] = mapped_column(String(255), nullable=True)

    customer_id: Mapped[UUID | None] = mapped_column(
        Uuid,
        ForeignKey("customers.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    payment_id: Mapped[UUID | None] = mapped_column(
        Uuid,
        ForeignKey("payments.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    payment_method_id: Mapped[UUID | None] = mapped_column(
        Uuid,
        ForeignKey("payment_methods.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    @declared_attr
    def session(cls) -> Mapped["FileShareSession"]:
        return relationship("FileShareSession", lazy="raise")

    @declared_attr
    def customer(cls) -> Mapped["Customer | None"]:
        return relationship("Customer", lazy="raise")

    @declared_attr
    def payment(cls) -> Mapped["Payment | None"]:
        return relationship("Payment", lazy="raise")
