"""Payment record model with processor metadata and risk scoring.

Stores the outcome of a single charge attempt, including the payment
method details, Stripe processor metadata, decline reasons, and risk
assessment.  Hybrid properties allow filtering on status in both Python
and SQL contexts.
"""

from enum import StrEnum
from typing import TYPE_CHECKING, Any, Literal, Self
from uuid import UUID

from sqlalchemy import ColumnElement, ForeignKey, SmallInteger, String, Uuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import Mapped, declared_attr, mapped_column, relationship
from sqlalchemy.sql.sqltypes import Integer

from rapidly.core.db.models import BaseEntity
from rapidly.core.extensions.sqlalchemy.types import StrEnumType
from rapidly.enums import PaymentProcessor

if TYPE_CHECKING:
    from .wallet import Wallet
    from .workspace import Workspace

# ISO 4217 currency code length.
_CURRENCY_CODE_LENGTH: int = 3


# ── Status enum ───────────────────────────────────────────────────────


class PaymentStatus(StrEnum):
    """Terminal or in-flight state of a charge attempt."""

    pending = "pending"
    succeeded = "succeeded"
    failed = "failed"

    @classmethod
    def from_stripe_charge(
        cls, stripe_status: Literal["failed", "pending", "succeeded"]
    ) -> Self:
        """Map a Stripe charge status string to the internal enum."""
        return cls(stripe_status)


# ── Payment model ─────────────────────────────────────────────────────


class Payment(BaseEntity):
    """One charge attempt with processor metadata, risk scoring, and decline info."""

    __tablename__ = "payments"

    # ── Processor & status ─────────────────────────────────────────────

    processor: Mapped[PaymentProcessor] = mapped_column(
        StrEnumType(PaymentProcessor), index=True, nullable=False
    )
    status: Mapped[PaymentStatus] = mapped_column(
        StrEnumType(PaymentStatus), index=True, nullable=False
    )

    # ── Amounts ────────────────────────────────────────────────────────

    amount: Mapped[int] = mapped_column(Integer, nullable=False)
    currency: Mapped[str] = mapped_column(String(_CURRENCY_CODE_LENGTH), nullable=False)

    # ── Method details ─────────────────────────────────────────────────

    method: Mapped[str] = mapped_column(String, index=True, nullable=False)
    method_metadata: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict
    )
    processor_metadata: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict
    )
    customer_email: Mapped[str | None] = mapped_column(
        String, nullable=True, index=True
    )

    processor_id: Mapped[str] = mapped_column(
        String, index=True, nullable=False, unique=True
    )

    # ── Decline information ────────────────────────────────────────────

    decline_reason: Mapped[str | None] = mapped_column(String, nullable=True)
    decline_message: Mapped[str | None] = mapped_column(String, nullable=True)

    # ── Risk assessment ────────────────────────────────────────────────

    risk_level: Mapped[str | None] = mapped_column(String, nullable=True)
    risk_score: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)

    # ── Relationships ──────────────────────────────────────────────────

    workspace_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("workspaces.id", ondelete="cascade"),
        nullable=False,
        index=True,
    )

    @declared_attr
    def workspace(cls) -> Mapped["Workspace"]:
        return relationship("Workspace", lazy="raise")

    wallet_id: Mapped[UUID | None] = mapped_column(
        Uuid,
        ForeignKey("wallets.id", ondelete="set null"),
        nullable=True,
        index=True,
    )

    @declared_attr
    def wallet(cls) -> Mapped["Wallet | None"]:
        return relationship("Wallet", lazy="raise")

    # ── Hybrid status checks ──────────────────────────────────────────

    @hybrid_property
    def is_succeeded(self) -> bool:
        return self.status == PaymentStatus.succeeded

    @is_succeeded.inplace.expression
    @classmethod
    def _is_succeeded_expression(cls) -> ColumnElement[bool]:
        return cls.status == PaymentStatus.succeeded

    @hybrid_property
    def is_failed(self) -> bool:
        return self.status == PaymentStatus.failed

    @is_failed.inplace.expression
    @classmethod
    def _is_failed_expression(cls) -> ColumnElement[bool]:
        return cls.status == PaymentStatus.failed
