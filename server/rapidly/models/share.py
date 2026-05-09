"""Share catalogue model with full-text search.

A share is the top-level sellable entity in the catalogue.  Each
share owns one or more ``SharePrice`` rows, optional media
attachments, and custom fields.
"""

from enum import StrEnum
from typing import TYPE_CHECKING
from uuid import UUID

from alembic_utils.pg_function import PGFunction
from alembic_utils.pg_trigger import PGTrigger
from alembic_utils.replaceable_entity import register_entities
from sqlalchemy import (
    Boolean,
    ForeignKey,
    Index,
    Text,
    Uuid,
)
from sqlalchemy.dialects.postgresql import CITEXT, TSVECTOR
from sqlalchemy.ext.associationproxy import AssociationProxy, association_proxy
from sqlalchemy.orm import Mapped, declared_attr, mapped_column, relationship

from rapidly.core.db.models import BaseEntity
from rapidly.core.extensions.sqlalchemy import StringEnum
from rapidly.core.metadata import MetadataMixin

from .share_price import SharePrice

if TYPE_CHECKING:
    from rapidly.models import (
        ShareCustomField,
        ShareMedia,
        Workspace,
    )
    from rapidly.models.file import ShareMediaFile


# -- Enums -------------------------------------------------------------------


class ShareVisibility(StrEnum):
    """Publishing lifecycle state for storefront exposure."""

    draft = "draft"
    private = "private"
    public = "public"


# -- Share model -----------------------------------------------------------


class Share(MetadataMixin, BaseEntity):
    """Sellable catalogue item with prices, media, and custom fields."""

    __tablename__ = "shares"
    __table_args__ = (
        Index(
            "ix_shares_search_vector",
            "search_vector",
            postgresql_using="gin",
        ),
    )

    # -- Workspace association -----------------------------------------------

    workspace_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("workspaces.id", ondelete="cascade"),
        nullable=False,
        index=True,
    )

    @declared_attr
    def workspace(cls) -> Mapped["Workspace"]:
        return relationship("Workspace", lazy="raise", back_populates="all_shares")

    # -- Core fields ---------------------------------------------------------

    name: Mapped[str] = mapped_column(CITEXT(), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_archived: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    visibility: Mapped[ShareVisibility | None] = mapped_column(
        StringEnum(ShareVisibility),
        nullable=True,
        default=ShareVisibility.public,
    )

    # -- Full-text search ----------------------------------------------------

    search_vector: Mapped[str] = mapped_column(TSVECTOR, nullable=True, deferred=True)

    # -- Price relationships -------------------------------------------------

    @declared_attr
    def all_prices(cls) -> Mapped[list["SharePrice"]]:
        return relationship(
            "SharePrice", lazy="raise", cascade="all", back_populates="share"
        )

    @declared_attr
    def prices(cls) -> Mapped[list["SharePrice"]]:
        # Active catalogue prices are needed in almost every context
        return relationship(
            "SharePrice",
            lazy="selectin",
            primaryjoin=(
                "and_("
                "SharePrice.share_id == Share.id, "
                "SharePrice.is_archived.is_(False), "
                "SharePrice.source == 'catalog'"
                ")"
            ),
            order_by="SharePrice.created_at",
            viewonly=True,
        )

    # -- Media attachments ---------------------------------------------------

    share_medias: Mapped[list["ShareMedia"]] = relationship(
        lazy="raise",
        order_by="ShareMedia.order",
        cascade="all, delete-orphan",
        back_populates="share",
    )

    medias: AssociationProxy[list["ShareMediaFile"]] = association_proxy(
        "share_medias", "file"
    )

    # -- Custom fields -------------------------------------------------------

    attached_custom_fields: Mapped[list["ShareCustomField"]] = relationship(
        lazy="raise",
        order_by="ShareCustomField.order",
        cascade="all, delete-orphan",
        back_populates="share",
    )

    # -- Price lookup --------------------------------------------------------

    def get_price(
        self, id: UUID, *, include_archived: bool = False
    ) -> "SharePrice | None":
        """Find a price by ID among this share's prices."""
        source = self.all_prices if include_archived else self.prices
        for price in source:
            if price.id == id:
                return price
        return None


# -- Postgres full-text search infrastructure --------------------------------

shares_search_vector_update_function = PGFunction(
    schema="public",
    signature="shares_search_vector_update()",
    definition="""
    RETURNS trigger AS $$
    BEGIN
        NEW.search_vector := to_tsvector('english', coalesce(NEW.name, '') || ' ' || coalesce(NEW.description, ''));
        RETURN NEW;
    END
    $$ LANGUAGE plpgsql;
    """,
)

shares_search_vector_trigger = PGTrigger(
    schema="public",
    signature="shares_search_vector_trigger",
    on_entity="shares",
    definition="""
    BEFORE INSERT OR UPDATE ON shares
    FOR EACH ROW EXECUTE FUNCTION shares_search_vector_update();
    """,
)

register_entities(
    (
        shares_search_vector_update_function,
        shares_search_vector_trigger,
    )
)
