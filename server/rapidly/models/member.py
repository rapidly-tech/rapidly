"""Team member model with role hierarchy and linked OAuth accounts.

A ``Member`` belongs to a ``Customer`` and inherits its workspace scope.
Uniqueness constraints ensure at most one member per (customer, email) and
(customer, external_id) pair.
"""

import dataclasses
from enum import StrEnum
from typing import Any
from uuid import UUID

from sqlalchemy import ForeignKey, String, UniqueConstraint, Uuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, declared_attr, mapped_column, relationship

from rapidly.core.db.models import BaseEntity
from rapidly.models.customer import (
    Customer,
    CustomerOAuthAccount,
    CustomerOAuthPlatform,
)

# ── Role enum ──────────────────────────────────────────────────────────


class MemberRole(StrEnum):
    """Hierarchical role within a customer team."""

    owner = "owner"
    billing_manager = "billing_manager"
    member = "member"


# ── Member model ───────────────────────────────────────────────────────


class Member(BaseEntity):
    """A named seat within a customer team, with optional OAuth linkage."""

    __tablename__ = "members"
    __table_args__ = (
        UniqueConstraint(
            "customer_id",
            "email",
            name="members_customer_id_email_key",
            postgresql_nulls_not_distinct=True,
        ),
        UniqueConstraint(
            "customer_id",
            "external_id",
            name="members_customer_id_external_id_key",
            postgresql_nulls_not_distinct=False,
        ),
    )

    customer_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("customers.id", ondelete="restrict"),
        nullable=False,
        index=True,
    )

    workspace_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("workspaces.id", ondelete="restrict"),
        nullable=False,
        index=True,
    )

    email: Mapped[str] = mapped_column(String(320), nullable=False)
    name: Mapped[str | None] = mapped_column(String, nullable=True, default=None)
    external_id: Mapped[str | None] = mapped_column(String, nullable=True, default=None)

    role: Mapped[MemberRole] = mapped_column(
        String, nullable=False, default=MemberRole.member
    )

    _oauth_accounts: Mapped[dict[str, dict[str, Any]]] = mapped_column(
        "oauth_accounts", JSONB, nullable=False, default=dict
    )

    @declared_attr
    def customer(cls) -> Mapped["Customer"]:
        return relationship("Customer", lazy="raise", back_populates="members")

    def get_oauth_account(
        self, account_id: str, platform: CustomerOAuthPlatform
    ) -> CustomerOAuthAccount | None:
        oauth_account_data = self._oauth_accounts.get(
            platform.get_account_key(account_id)
        )
        if oauth_account_data is None:
            return None

        return CustomerOAuthAccount(**oauth_account_data)

    def set_oauth_account(
        self, oauth_account: CustomerOAuthAccount, platform: CustomerOAuthPlatform
    ) -> None:
        account_key = platform.get_account_key(oauth_account.account_id)
        self._oauth_accounts = {
            **self._oauth_accounts,
            account_key: dataclasses.asdict(oauth_account),
        }

    def remove_oauth_account(
        self, account_id: str, platform: CustomerOAuthPlatform
    ) -> None:
        account_key = platform.get_account_key(account_id)
        self._oauth_accounts = {
            k: v for k, v in self._oauth_accounts.items() if k != account_key
        }

    @property
    def oauth_accounts(self) -> dict[str, Any]:
        return self._oauth_accounts
