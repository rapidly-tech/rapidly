"""User and OAuth account models.

``User`` is an interactive dashboard user -- a creator, admin, or
team member.  ``OAuthAccount`` stores linked identity-provider
credentials and implements automatic token-refresh scheduling.
"""

import time
from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from sqlalchemy import (
    TIMESTAMP,
    Boolean,
    Column,
    ColumnElement,
    ForeignKey,
    Integer,
    String,
    Text,
    Uuid,
    and_,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import Mapped, declared_attr, mapped_column, relationship
from sqlalchemy.schema import Index, UniqueConstraint

from rapidly.core.db.models import BaseEntity
from rapidly.core.extensions.sqlalchemy.types import StringEnum
from rapidly.core.types import Schema

from .account import Account

# Tokens expiring within this window (seconds) should be proactively refreshed.
_TOKEN_REFRESH_WINDOW: int = 1800


# -- Enumerations -----------------------------------------------------------


class OAuthPlatform(StrEnum):
    """Supported third-party identity providers."""

    microsoft = "microsoft"
    google = "google"
    apple = "apple"


class IdentityVerificationStatus(StrEnum):
    """Stripe Identity verification lifecycle."""

    unverified = "unverified"
    pending = "pending"
    verified = "verified"
    failed = "failed"

    @property
    def display_name(self) -> str:
        """Human-readable status label."""
        return self.value.capitalize()

    def get_display_name(self) -> str:
        return self.display_name


# -- OAuthAccount model ------------------------------------------------------


class OAuthAccount(BaseEntity):
    """Linked third-party identity-provider credentials for a user."""

    __tablename__ = "oauth_accounts"
    __table_args__ = (
        UniqueConstraint("platform", "account_id"),
        Index("idx_user_id_platform", "user_id", "platform"),
    )

    # -- Provider info -------------------------------------------------------

    platform: Mapped[OAuthPlatform] = mapped_column(String(32), nullable=False)
    account_id: Mapped[str] = mapped_column(String(320), nullable=False)
    account_email: Mapped[str] = mapped_column(String(320), nullable=False)
    account_username: Mapped[str | None] = mapped_column(String(320), nullable=True)

    # -- Token storage -------------------------------------------------------

    access_token: Mapped[str] = mapped_column(String(4096), nullable=False)
    expires_at: Mapped[int | None] = mapped_column(Integer, nullable=True, default=None)
    refresh_token: Mapped[str | None] = mapped_column(
        String(4096), nullable=True, default=None
    )
    refresh_token_expires_at: Mapped[int | None] = mapped_column(
        Integer, nullable=True, default=None
    )

    # -- User association ----------------------------------------------------

    user_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("users.id", ondelete="cascade"),
        nullable=False,
    )

    user: Mapped["User"] = relationship("User", back_populates="oauth_accounts")

    # -- Token lifecycle helpers ---------------------------------------------

    def is_access_token_expired(self) -> bool:
        """Check whether the access token has already expired."""
        if self.expires_at is None:
            return False
        return time.time() > self.expires_at

    def should_refresh_access_token(
        self, unless_ttl_gt: int = _TOKEN_REFRESH_WINDOW
    ) -> bool:
        """Determine if the token should be proactively refreshed."""
        return bool(
            self.expires_at
            and self.refresh_token
            and self.expires_at <= (time.time() + unless_ttl_gt)
        )


# -- User model --------------------------------------------------------------


class User(BaseEntity):
    """An interactive dashboard user with identity verification and OAuth."""

    __tablename__ = "users"
    __table_args__ = (
        Index(
            "ix_users_email_case_insensitive", func.lower(Column("email")), unique=True
        ),
    )

    # -- Core identity -------------------------------------------------------

    email: Mapped[str] = mapped_column(String(320), nullable=False)
    email_verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    avatar_url: Mapped[str | None] = mapped_column(Text, nullable=True, default=None)
    is_admin: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # -- Payout account ------------------------------------------------------

    account_id: Mapped[UUID | None] = mapped_column(
        Uuid,
        ForeignKey("accounts.id", ondelete="set null"),
        nullable=True,
    )

    @declared_attr
    def account(cls) -> Mapped[Account | None]:
        return relationship(
            Account,
            lazy="raise",
            back_populates="users",
            foreign_keys="[User.account_id]",
        )

    # -- OAuth accounts ------------------------------------------------------

    @declared_attr
    def oauth_accounts(cls) -> Mapped[list[OAuthAccount]]:
        return relationship(OAuthAccount, lazy="joined", back_populates="user")

    # -- Legal and billing ---------------------------------------------------

    accepted_terms_of_service: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    stripe_customer_id: Mapped[str | None] = mapped_column(
        String, nullable=True, default=None, unique=True
    )

    # -- Identity verification -----------------------------------------------

    identity_verification_status: Mapped[IdentityVerificationStatus] = mapped_column(
        StringEnum(IdentityVerificationStatus),
        nullable=False,
        default=IdentityVerificationStatus.unverified,
    )
    identity_verification_id: Mapped[str | None] = mapped_column(
        String, nullable=True, default=None, unique=True
    )

    @property
    def identity_verified(self) -> bool:
        return self.identity_verification_status == IdentityVerificationStatus.verified

    # -- Suspension ----------------------------------------------------------

    blocked_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=True,
        default=None,
    )

    # -- Extensible metadata -------------------------------------------------

    meta: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)

    # -- Authentication predicate --------------------------------------------

    @hybrid_property
    def can_authenticate(self) -> bool:
        """A user may authenticate if not deleted and not blocked."""
        return self.deleted_at is None and self.blocked_at is None

    @can_authenticate.inplace.expression
    @classmethod
    def _can_authenticate_expression(cls) -> ColumnElement[bool]:
        return and_(cls.deleted_at.is_(None), cls.blocked_at.is_(None))

    # -- Signup tracking -----------------------------------------------------

    @property
    def signup_attribution(self) -> dict[str, Any]:
        """Retrieve the signup attribution metadata, if any."""
        return self.meta.get("signup", {})

    @signup_attribution.setter
    def signup_attribution(self, value: dict[str, Any] | Schema | None) -> None:
        if not value:
            return

        meta = self.meta or {}
        if isinstance(value, Schema):
            value = value.model_dump(exclude_unset=True)

        meta["signup"] = value
        self.meta = meta

    @property
    def had_creator_signup_intent(self) -> bool:
        return self.signup_attribution.get("intent") == "creator"

    @property
    def campaign_code(self) -> str | None:
        return self.signup_attribution.get("campaign")

    # -- OAuth helpers -------------------------------------------------------

    def get_oauth_account(self, platform: OAuthPlatform) -> OAuthAccount | None:
        """Find the linked OAuth account for the given provider."""
        return next(
            (acct for acct in self.oauth_accounts if acct.platform == platform),
            None,
        )

    def get_microsoft_account(self) -> OAuthAccount | None:
        return self.get_oauth_account(OAuthPlatform.microsoft)

    # -- Display helpers -----------------------------------------------------

    @property
    def posthog_distinct_id(self) -> str:
        return f"user:{self.id}"

    @property
    def public_name(self) -> str:
        """Best-effort display name: Microsoft display name, then email initial."""
        ms = self.get_microsoft_account()
        if ms is not None and ms.account_username:
            return ms.account_username
        return self.email[0]

    @property
    def microsoft_username(self) -> str | None:
        ms = self.get_microsoft_account()
        return ms.account_username if ms is not None else None
