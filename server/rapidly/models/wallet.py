"""Customer wallet model with computed balance from transactions.

Each customer may have one wallet per (type, currency) combination.
The ``balance`` is a read-only column property computed as the
aggregate sum of linked ``WalletTransaction`` rows.
"""

from enum import StrEnum
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import ForeignKey, String, UniqueConstraint, Uuid, func, select
from sqlalchemy.ext.associationproxy import AssociationProxy, association_proxy
from sqlalchemy.orm import (
    Mapped,
    column_property,
    declared_attr,
    mapped_column,
    relationship,
)

from rapidly.core.db.models.base import BaseEntity
from rapidly.core.extensions.sqlalchemy.types import StringEnum

if TYPE_CHECKING:
    from .customer import Customer
    from .workspace import Workspace

# ISO 4217 currency code length.
_CURRENCY_CODE_LENGTH: int = 3


class WalletType(StrEnum):
    """Wallet purpose: metered usage tracking or prepaid billing credit."""

    usage = "usage"
    billing = "billing"


class Wallet(BaseEntity):
    """Ledger-style wallet whose balance is the sum of its transactions."""

    __tablename__ = "wallets"
    __table_args__ = (UniqueConstraint("type", "currency", "customer_id"),)

    type: Mapped[WalletType] = mapped_column(StringEnum(WalletType), nullable=False)
    currency: Mapped[str] = mapped_column(String(_CURRENCY_CODE_LENGTH))
    customer_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("customers.id", ondelete="cascade"),
        unique=True,
    )

    @declared_attr
    def customer(cls) -> Mapped["Customer"]:
        return relationship("Customer", lazy="raise_on_sql")

    workspace: AssociationProxy["Workspace"] = association_proxy(
        "customer", "workspace"
    )

    @declared_attr
    def balance(cls) -> Mapped[int]:
        """Computed column: aggregate sum of all wallet transactions (defaults to 0)."""
        from .wallet_transaction import WalletTransaction

        return column_property(
            select(func.coalesce(func.sum(WalletTransaction.amount), 0))
            .where(WalletTransaction.wallet_id == cls.id)
            .correlate_except(WalletTransaction)
            .scalar_subquery()
        )
