"""ORM model for wallet balance ledger entries."""

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import TIMESTAMP, ForeignKey, String, Uuid
from sqlalchemy.orm import Mapped, declared_attr, mapped_column, relationship
from sqlalchemy.sql.sqltypes import BigInteger

from rapidly.core.db.models import UUIDModel
from rapidly.core.utils import now_utc

if TYPE_CHECKING:
    from .wallet import Wallet


class WalletTransaction(UUIDModel):
    """Records a ledger entry for a wallet balance change."""

    __tablename__ = "wallet_transactions"

    timestamp: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, default=now_utc, index=True
    )
    currency: Mapped[str] = mapped_column(String(3))
    amount: Mapped[int] = mapped_column(BigInteger)
    wallet_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("wallets.id", ondelete="restrict"), index=True
    )

    @declared_attr
    def wallet(cls) -> Mapped["Wallet"]:
        return relationship("Wallet", lazy="raise_on_sql")
