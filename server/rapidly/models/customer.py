"""Customer model with short-ID generation, OAuth linking, and full-text search.

Customers belong to a workspace and represent the end-users who
purchase products or access the customer portal.  A customer may
transition from ``individual`` to ``team`` when they purchase a
seat-based share (this upgrade is one-way).

Short IDs are generated via a Postgres function based on Instagram's
epoch-sharded-ID scheme.
"""

import dataclasses
import string
import time
from collections.abc import Sequence
from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING, Any
from uuid import UUID

import sqlalchemy as sa
from alembic_utils.pg_function import PGFunction
from alembic_utils.pg_trigger import PGTrigger
from alembic_utils.replaceable_entity import register_entities
from sqlalchemy import (
    TIMESTAMP,
    Boolean,
    Column,
    ColumnElement,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import Mapped, declared_attr, mapped_column, relationship

from rapidly.core.address import Address, AddressType
from rapidly.core.db.models import BaseEntity
from rapidly.core.metadata import MetadataMixin

if TYPE_CHECKING:
    from .member import Member
    from .payment_method import PaymentMethod
    from .workspace import Workspace

# -- Short-ID encoding -------------------------------------------------------

_BASE26_CHARS: str = string.ascii_uppercase
_SHORT_ID_WIDTH: int = 8


def short_id_to_base26(short_id: int) -> str:
    """Encode a numeric short_id as an 8-character uppercase alphabetic string."""
    chars: list[str] = []
    remaining = short_id

    while remaining > 0:
        chars.append(_BASE26_CHARS[remaining % 26])
        remaining //= 26

    return "".join(reversed(chars)).rjust(_SHORT_ID_WIDTH, "A")


# -- Customer OAuth helpers ---------------------------------------------------


class CustomerOAuthPlatform(StrEnum):
    """Platforms a customer may link for single sign-on."""

    microsoft = "microsoft"
    discord = "discord"

    def get_account_key(self, account_id: str) -> str:
        """Construct the JSONB key for an OAuth account entry."""
        return f"{self.value}:{account_id}"

    def get_account_id(self, data: dict[str, Any]) -> str:
        if self == CustomerOAuthPlatform.microsoft:
            return str(data["id"])
        if self == CustomerOAuthPlatform.discord:
            return str(data["id"])
        raise NotImplementedError()

    def get_account_username(self, data: dict[str, Any]) -> str:
        if self == CustomerOAuthPlatform.microsoft:
            return data.get("displayName") or data.get("userPrincipalName", "")
        if self == CustomerOAuthPlatform.discord:
            return data["username"]
        raise NotImplementedError()


@dataclasses.dataclass
class CustomerOAuthAccount:
    """Transient representation of a linked customer OAuth credential."""

    access_token: str
    account_id: str
    account_username: str | None = None
    expires_at: int | None = None
    refresh_token: str | None = None
    refresh_token_expires_at: int | None = None

    def is_expired(self) -> bool:
        if self.expires_at is None:
            return False
        return time.time() > self.expires_at


# -- Customer type ------------------------------------------------------------


class CustomerType(StrEnum):
    """Lifecycle type: individual (B2C) or team (seat-based)."""

    individual = "individual"
    team = "team"


# -- Customer model -----------------------------------------------------------


class Customer(MetadataMixin, BaseEntity):
    """A workspace's end-user with billing, OAuth, and full-text search."""

    __tablename__ = "customers"
    __table_args__ = (
        Index(
            "ix_customers_email_case_insensitive",
            func.lower(Column("email")),
            "deleted_at",
            postgresql_nulls_not_distinct=True,
        ),
        Index(
            "ix_customers_workspace_id_email_case_insensitive",
            func.lower(Column("email")),
            "deleted_at",
            unique=True,
            postgresql_nulls_not_distinct=True,
        ),
        Index(
            "ix_customers_external_id_pattern",
            "external_id",
            postgresql_ops={"external_id": "text_pattern_ops"},
        ),
        Index(
            "ix_customers_search_vector",
            "search_vector",
            postgresql_using="gin",
        ),
        UniqueConstraint("workspace_id", "external_id"),
        UniqueConstraint("workspace_id", "short_id"),
    )
    short_id_sequence = sa.Sequence("customer_short_id_seq", start=1)

    # -- Workspace association -----------------------------------------------

    workspace_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("workspaces.id", ondelete="cascade"),
        nullable=False,
        index=True,
    )

    @declared_attr
    def workspace(cls) -> Mapped["Workspace"]:
        return relationship("Workspace", lazy="raise")

    # -- Customer type -------------------------------------------------------

    type: Mapped[CustomerType | None] = mapped_column(
        String,
        nullable=True,
        default=CustomerType.individual,
    )

    # -- Identity fields -----------------------------------------------------

    external_id: Mapped[str | None] = mapped_column(String, nullable=True, default=None)
    short_id: Mapped[int] = mapped_column(
        sa.BigInteger,
        nullable=False,
        index=True,
        server_default=sa.text("generate_customer_short_id()"),
    )
    email: Mapped[str] = mapped_column(String(320), nullable=False)
    email_verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    name: Mapped[str | None] = mapped_column(String, nullable=True, default=None)

    # -- Billing details -----------------------------------------------------

    stripe_customer_id: Mapped[str | None] = mapped_column(
        String, nullable=True, default=None, unique=False
    )
    _billing_name: Mapped[str | None] = mapped_column(
        "billing_name", String, nullable=True, default=None
    )
    billing_address: Mapped[Address | None] = mapped_column(
        AddressType, nullable=True, default=None
    )
    invoice_next_number: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    # -- Default payment method ----------------------------------------------

    default_payment_method_id: Mapped[UUID | None] = mapped_column(
        Uuid,
        ForeignKey("payment_methods.id", ondelete="set null"),
        nullable=True,
        default=None,
        index=True,
    )

    @declared_attr
    def default_payment_method(cls) -> Mapped["PaymentMethod | None"]:
        return relationship(
            "PaymentMethod",
            lazy="raise",
            uselist=False,
            foreign_keys="[Customer.default_payment_method_id]",
        )

    @declared_attr
    def payment_methods(cls) -> Mapped[list["PaymentMethod"]]:
        return relationship(
            "PaymentMethod",
            lazy="raise",
            back_populates="customer",
            cascade="all, delete-orphan",
            foreign_keys="[PaymentMethod.customer_id]",
        )

    # -- OAuth accounts (JSONB) ----------------------------------------------

    _oauth_accounts: Mapped[dict[str, dict[str, Any]]] = mapped_column(
        "oauth_accounts", JSONB, nullable=False, default=dict
    )

    # -- Legacy user bridge --------------------------------------------------

    _legacy_user_id: Mapped[UUID | None] = mapped_column(
        "legacy_user_id",
        Uuid,
        ForeignKey("users.id", ondelete="set null"),
        nullable=True,
    )

    # -- Metering timestamps -------------------------------------------------

    meters_dirtied_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True, default=None, index=True, deferred=True
    )
    meters_updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True, default=None, index=True, deferred=True
    )

    # -- Full-text search ----------------------------------------------------

    search_vector: Mapped[str] = mapped_column(TSVECTOR, nullable=True, deferred=True)

    # -- Member relationship -------------------------------------------------

    @declared_attr
    def members(cls) -> Mapped[Sequence["Member"]]:
        return relationship(
            "Member",
            lazy="raise",
            back_populates="customer",
            cascade="all, delete-orphan",
        )

    # -- Authentication predicate --------------------------------------------

    @hybrid_property
    def can_authenticate(self) -> bool:
        """A customer may authenticate if not soft-deleted."""
        return self.deleted_at is None

    @can_authenticate.inplace.expression
    @classmethod
    def _can_authenticate_expression(cls) -> ColumnElement[bool]:
        return cls.deleted_at.is_(None)

    # -- OAuth account management --------------------------------------------

    def get_oauth_account(
        self, account_id: str, platform: CustomerOAuthPlatform
    ) -> CustomerOAuthAccount | None:
        key = platform.get_account_key(account_id)
        raw = self._oauth_accounts.get(key)
        if raw is None:
            return None
        return CustomerOAuthAccount(**raw)

    def set_oauth_account(
        self, oauth_account: CustomerOAuthAccount, platform: CustomerOAuthPlatform
    ) -> None:
        key = platform.get_account_key(oauth_account.account_id)
        self._oauth_accounts = {
            **self._oauth_accounts,
            key: dataclasses.asdict(oauth_account),
        }

    def remove_oauth_account(
        self, account_id: str, platform: CustomerOAuthPlatform
    ) -> None:
        key = platform.get_account_key(account_id)
        self._oauth_accounts = {
            k: v for k, v in self._oauth_accounts.items() if k != key
        }

    @property
    def oauth_accounts(self) -> dict[str, Any]:
        return self._oauth_accounts

    # -- Short ID display ----------------------------------------------------

    @property
    def short_id_str(self) -> str:
        """Base-26 alphabetic representation of the numeric short_id."""
        return short_id_to_base26(self.short_id)

    # -- Billing name --------------------------------------------------------

    @property
    def billing_name(self) -> str | None:
        """Fall back to display name when no explicit billing name is set."""
        return self._billing_name or self.name

    @billing_name.setter
    def billing_name(self, value: str | None) -> None:
        self._billing_name = value


# -- Postgres functions and triggers ------------------------------------------

generate_customer_short_id_function = PGFunction(
    schema="public",
    signature="generate_customer_short_id(creation_timestamp TIMESTAMP WITH TIME ZONE DEFAULT clock_timestamp())",
    definition="""
    RETURNS bigint AS $$
    DECLARE
        our_epoch bigint := 1672531200000; -- 2023-01-01 in milliseconds
        seq_id bigint;
        now_millis bigint;
        result bigint;
    BEGIN
        -- Get sequence number modulo 1024 (10 bits)
        SELECT nextval('customer_short_id_seq') % 1024 INTO seq_id;

        -- Use provided timestamp (defaults to clock_timestamp())
        SELECT FLOOR(EXTRACT(EPOCH FROM creation_timestamp) * 1000) INTO now_millis;

        -- 42 bits timestamp (milliseconds) | 10 bits sequence = 52 bits total
        -- Capacity: 1,024 IDs per millisecond (over 1 million per second)
        -- Combine: (timestamp - epoch) << 10 | sequence
        result := (now_millis - our_epoch) << 10;
        result := result | seq_id;

        RETURN result;
    END;
    $$ LANGUAGE plpgsql;
    """,
)


customers_search_vector_update_function = PGFunction(
    schema="public",
    signature="customers_search_vector_update()",
    definition="""
    RETURNS trigger AS $$
    BEGIN
        NEW.search_vector := to_tsvector('simple', coalesce(NEW.name, ''));
        RETURN NEW;
    END
    $$ LANGUAGE plpgsql;
    """,
)

customers_search_vector_trigger = PGTrigger(
    schema="public",
    signature="customers_search_vector_trigger",
    on_entity="customers",
    definition="""
    BEFORE INSERT OR UPDATE ON customers
    FOR EACH ROW EXECUTE FUNCTION customers_search_vector_update();
    """,
)

register_entities(
    (
        generate_customer_short_id_function,
        customers_search_vector_update_function,
        customers_search_vector_trigger,
    )
)
