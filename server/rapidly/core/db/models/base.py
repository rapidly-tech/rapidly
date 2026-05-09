"""Declarative ORM foundations for the Rapidly schema.

Provides the base classes that all persistent models inherit from.  The
inheritance tree is designed so that each cross-cutting concern -- primary
key strategy, lifecycle tracking, rate limiting -- is a separate layer
that can be composed independently:

    Model            -- declarative root with shared MetaData
    UUIDModel        -- UUID4 primary key and value-based equality
    AuditableModel   -- created / modified / soft-delete timestamps
    BaseEntity       -- UUID + audit (the common choice for domain tables)
    RateLimitMixin   -- per-entity rate-limit tier column
"""

from datetime import datetime
from uuid import UUID

from alembic_utils.pg_extension import PGExtension
from alembic_utils.replaceable_entity import register_entities
from sqlalchemy import TIMESTAMP, MetaData, Uuid, inspect
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from rapidly.core.extensions.sqlalchemy.types import StringEnum
from rapidly.core.utils import create_uuid, now_utc
from rapidly.enums import RateLimitGroup

# ---------------------------------------------------------------------------
# Constraint naming
# ---------------------------------------------------------------------------
# A fixed naming scheme guarantees that Alembic auto-generates reproducible
# migration files regardless of which machine or CI runner creates them.

_NAMING_CONVENTION: dict[str, str] = {
    "pk": "%(table_name)s_pkey",
    "fk": "%(table_name)s_%(column_0_N_name)s_fkey",
    "ix": "ix_%(column_0_N_label)s",
    "uq": "%(table_name)s_%(column_0_N_name)s_key",
    "ck": "%(table_name)s_%(constraint_name)s_check",
}

# Single MetaData instance shared by every model in the application so
# that Alembic and ``create_all`` discover the full schema in one pass.
my_metadata = MetaData(naming_convention=_NAMING_CONVENTION)


# ---------------------------------------------------------------------------
# PostgreSQL extensions that must exist before tables are created
# ---------------------------------------------------------------------------

_pg_uuid_ossp = PGExtension(schema="public", signature="uuid-ossp")
_pg_citext = PGExtension(schema="public", signature="citext")
register_entities((_pg_uuid_ossp, _pg_citext))

uuid_ossp = _pg_uuid_ossp
citext = _pg_citext


# ---------------------------------------------------------------------------
# Declarative root
# ---------------------------------------------------------------------------


class Model(DeclarativeBase):
    """Root base for all Rapidly tables.

    Carries the shared :pyattr:`metadata` but defines no columns of its
    own.  Lightweight tables (e.g. many-to-many association rows) can
    inherit directly from ``Model`` to stay column-free.
    """

    __abstract__ = True
    metadata = my_metadata


# ---------------------------------------------------------------------------
# UUID primary key
# ---------------------------------------------------------------------------


class UUIDModel(Model):
    """Adds a UUID4 primary key and identity-based equality semantics.

    IDs are generated in application memory (via ``create_uuid``) so
    that related objects can reference each other before any database
    round-trip.  Equality and hashing are driven solely by ``id``,
    making set operations safe across different session instances.
    """

    __abstract__ = True

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=create_uuid)

    # -- equality & hashing ------------------------------------------------

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, self.__class__):
            return NotImplemented
        return self.id == other.id

    def __hash__(self) -> int:
        return self.id.int

    # -- display -----------------------------------------------------------

    def __repr__(self) -> str:
        state = inspect(self)
        pk = state.identity[0] if state.identity is not None else None
        return f"{self.__class__.__name__}(id={pk!r})"


# ---------------------------------------------------------------------------
# Lifecycle timestamps
# ---------------------------------------------------------------------------


class AuditableModel(Model):
    """Stamps every row with created / modified / soft-deleted times.

    All timestamps use ``TIMESTAMP WITH TIME ZONE`` so that PostgreSQL
    stores them as UTC-epoch microseconds.  The application always
    supplies UTC values through ``now_utc()``.

    Columns
    -------
    created_at
        Set once at INSERT via the default factory; indexed for
        chronological listings and billing-period filtering.
    modified_at
        Updated automatically by SQLAlchemy's ``onupdate`` callback
        whenever a flush detects dirty attributes.
    deleted_at
        Marks a row as soft-deleted.  Indexed so that retention-sweep
        jobs can efficiently locate expired records.
    """

    __abstract__ = True

    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, default=now_utc, index=True
    )
    modified_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), onupdate=now_utc, nullable=True, default=None
    )
    deleted_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True, default=None, index=True
    )

    # -- mutation helpers --------------------------------------------------

    def set_deleted_at(self) -> None:
        """Soft-delete this row by recording the current UTC instant."""
        self.deleted_at = now_utc()


# ---------------------------------------------------------------------------
# Standard domain base
# ---------------------------------------------------------------------------


class BaseEntity(UUIDModel, AuditableModel):
    """UUID primary key + full lifecycle timestamps.

    The default base for first-class business tables (products, orders,
    workspaces, etc.).  Use ``Model`` or ``UUIDModel`` for join tables
    or other lightweight mappings.
    """

    __abstract__ = True


# ---------------------------------------------------------------------------
# Rate-limit tier
# ---------------------------------------------------------------------------


class RateLimitMixin:
    """Column mixin that tags an entity with a rate-limit tier.

    Rapidly's gateway reads this column to decide per-workspace or
    per-token throughput ceilings without code changes.
    """

    __abstract__ = True

    rate_limit_group: Mapped[RateLimitGroup] = mapped_column(
        StringEnum(RateLimitGroup, length=16),
        nullable=False,
        default=RateLimitGroup.default,
    )
