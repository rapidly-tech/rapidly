"""Generic repository base, protocols, and mixins for SQLAlchemy models.

Layering
--------
1. ``Repository`` -- core CRUD + pagination for a single model type.
2. **Mixins** compose additional behaviour (soft-delete, id-lookup, sorting)
   and should appear *left* of ``Repository`` in the MRO.
3. **Protocols** express structural contracts that mixins depend on, allowing
   them to call ``self.get_base_statement()`` etc. without hard-coupling to
   the concrete ``Repository`` implementation.

Type-parameter conventions
--------------------------
* ``M`` -- the SQLAlchemy model type managed by the repository.
* ``ID_TYPE`` -- the Python type of the model's primary key column.
* ``PE`` -- a ``StrEnum`` that enumerates sortable properties.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator, Sequence
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Any, Protocol, Self

from sqlalchemy import Select, UnaryExpression, asc, desc, func, over, select
from sqlalchemy.orm import Mapped
from sqlalchemy.orm.attributes import flag_modified
from sqlalchemy.sql.base import ExecutableOption
from sqlalchemy.sql.expression import ColumnExpressionArgument

from rapidly.config import settings
from rapidly.core.db.postgres import AsyncReadSession, AsyncSession
from rapidly.core.ordering import Sorting
from rapidly.core.utils import now_utc

# ---------------------------------------------------------------------------
# Structural protocols
# ---------------------------------------------------------------------------


class ModelDeletedAtProtocol(Protocol):
    """Model that carries a ``deleted_at`` column."""

    deleted_at: Mapped[datetime | None]


class ModelIDProtocol[ID_TYPE](Protocol):
    """Model that carries a typed ``id`` column."""

    id: Mapped[ID_TYPE]


class ModelDeletedAtIDProtocol[ID_TYPE](Protocol):
    """Model with both ``id`` and ``deleted_at``."""

    id: Mapped[ID_TYPE]
    deleted_at: Mapped[datetime | None]


type Options = Sequence[ExecutableOption]


class DataAccessProtocol[M](Protocol):
    """Structural contract consumed by mixins.

    Mixins call ``self.get_base_statement()`` and ``self.update()`` etc.
    through this protocol so they don't depend on the concrete class.
    """

    model: type[M]

    async def get_one(self, statement: Select[tuple[M]]) -> M: ...
    async def get_one_or_none(self, statement: Select[tuple[M]]) -> M | None: ...
    async def get_all(self, statement: Select[tuple[M]]) -> Sequence[M]: ...

    async def paginate(
        self, statement: Select[tuple[M]], *, limit: int, page: int
    ) -> tuple[list[M], int]: ...

    def get_base_statement(self) -> Select[tuple[M]]: ...

    async def create(self, object: M, *, flush: bool = False) -> M: ...

    async def update(
        self,
        object: M,
        *,
        update_dict: dict[str, Any] | None = None,
        flush: bool = False,
    ) -> M: ...


# ---------------------------------------------------------------------------
# Page container
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Page[M]:
    """Result container for a page of query results with a total count."""

    items: Sequence[M]
    total: int


# ---------------------------------------------------------------------------
# Core repository
# ---------------------------------------------------------------------------


class Repository[M]:
    """CRUD primitives for a single SQLAlchemy model type.

    Subclasses extend behaviour by placing mixins to the *left* of
    ``Repository`` in the MRO.
    """

    model: type[M]

    __slots__ = ("session",)

    def __init__(self, session: AsyncSession | AsyncReadSession) -> None:
        self.session = session

    # -- reads -------------------------------------------------------------

    async def get_one(self, statement: Select[tuple[M]]) -> M:
        result = await self.session.execute(statement)
        return result.unique().scalar_one()

    async def get_one_or_none(self, statement: Select[tuple[M]]) -> M | None:
        result = await self.session.execute(statement)
        return result.unique().scalar_one_or_none()

    async def get_all(self, statement: Select[tuple[M]]) -> Sequence[M]:
        result = await self.session.execute(statement)
        return result.scalars().unique().all()

    async def stream(self, statement: Select[tuple[M]]) -> AsyncGenerator[M, None]:
        """Yield rows lazily without loading the full result set.

        Do **not** use with statements that join to-many relationships -- the
        driver-level stream cannot apply ``unique()``.
        """
        cursor = await self.session.stream_scalars(
            statement,
            execution_options={"yield_per": settings.DATABASE_STREAM_YIELD_PER},
        )
        try:
            async for row in cursor:
                yield row
        finally:
            await cursor.close()

    async def paginate(
        self, statement: Select[tuple[M]], *, limit: int, page: int
    ) -> tuple[list[M], int]:
        """Return ``(items, total_count)`` for the given page."""
        offset = (page - 1) * limit
        stmt: Select[tuple[M, int]] = (
            statement.add_columns(over(func.count())).limit(limit).offset(offset)
        )
        result = await self.session.execute(stmt)

        items: list[M] = []
        total = 0
        for row in result.unique().all():
            item, total = row._tuple()
            items.append(item)

        return items, total

    async def count(self, statement: Select[tuple[M]]) -> int:
        count_result = await self.session.execute(
            statement.with_only_columns(func.count())
        )
        return count_result.scalar_one()

    def get_base_statement(self) -> Select[tuple[M]]:
        return select(self.model)

    # -- writes ------------------------------------------------------------

    async def create(self, object: M, *, flush: bool = False) -> M:
        self.session.add(object)
        if flush:
            await self.session.flush()
        return object

    async def update(
        self,
        object: M,
        *,
        update_dict: dict[str, Any] | None = None,
        flush: bool = False,
    ) -> M:
        if update_dict is not None:
            for attr, value in update_dict.items():
                setattr(object, attr, value)
                try:
                    flag_modified(object, attr)
                except KeyError:
                    pass  # Attribute not tracked by SQLAlchemy.
        self.session.add(object)
        if flush:
            await self.session.flush()
        return object

    async def delete(self, obj: M, *, flush: bool = False) -> None:
        """Permanently remove a model instance."""
        await self.session.delete(obj)
        if flush:
            await self.session.flush()

    # -- construction ------------------------------------------------------

    @classmethod
    def from_session(cls, session: AsyncSession | AsyncReadSession) -> Self:
        return cls(session)


# ---------------------------------------------------------------------------
# Soft-delete mixin & protocol
# ---------------------------------------------------------------------------


class RepositorySoftDeleteProtocol[MODEL_DELETED_AT: ModelDeletedAtProtocol](
    DataAccessProtocol[MODEL_DELETED_AT], Protocol
):
    """Protocol expected by soft-delete-aware mixins."""

    def get_base_statement(
        self, *, include_deleted: bool = False
    ) -> Select[tuple[MODEL_DELETED_AT]]: ...

    async def soft_delete(
        self, object: MODEL_DELETED_AT, *, flush: bool = False
    ) -> MODEL_DELETED_AT: ...


class SoftDeleteMixin[MODEL_DELETED_AT: ModelDeletedAtProtocol]:
    """Overrides ``get_base_statement`` to exclude soft-deleted rows and
    adds a ``soft_delete`` helper."""

    def get_base_statement(
        self: DataAccessProtocol[MODEL_DELETED_AT],
        *,
        include_deleted: bool = False,
    ) -> Select[tuple[MODEL_DELETED_AT]]:
        stmt = super().get_base_statement()  # type: ignore[safe-super]
        if not include_deleted:
            stmt = stmt.where(self.model.deleted_at.is_(None))
        return stmt

    async def soft_delete(
        self: DataAccessProtocol[MODEL_DELETED_AT],
        object: MODEL_DELETED_AT,
        *,
        flush: bool = False,
    ) -> MODEL_DELETED_AT:
        return await self.update(
            object, update_dict={"deleted_at": now_utc()}, flush=flush
        )


# ---------------------------------------------------------------------------
# ID-based lookup mixins
# ---------------------------------------------------------------------------


class FindByIdMixin[MODEL_ID: ModelIDProtocol, ID_TYPE]:  # type: ignore[type-arg]
    """Adds ``get_by_id`` for models with a simple ``id`` column."""

    async def get_by_id(
        self: DataAccessProtocol[MODEL_ID],
        id: ID_TYPE,
        *,
        options: Options = (),
    ) -> MODEL_ID | None:
        stmt = self.get_base_statement().where(self.model.id == id).options(*options)
        return await self.get_one_or_none(stmt)


class SoftDeleteByIdMixin[
    MODEL_DELETED_AT_ID: ModelDeletedAtIDProtocol,  # type: ignore[type-arg]
    ID_TYPE,
]:
    """Adds ``get_by_id`` that respects soft-delete status."""

    async def get_by_id(
        self: RepositorySoftDeleteProtocol[MODEL_DELETED_AT_ID],
        id: ID_TYPE,
        *,
        options: Options = (),
        include_deleted: bool = False,
    ) -> MODEL_DELETED_AT_ID | None:
        stmt = (
            self.get_base_statement(include_deleted=include_deleted)
            .where(self.model.id == id)
            .options(*options)
        )
        return await self.get_one_or_none(stmt)


# ---------------------------------------------------------------------------
# Sorting mixin
# ---------------------------------------------------------------------------

type SortingClause = ColumnExpressionArgument[Any] | UnaryExpression[Any]


class SortableMixin[M, PE: StrEnum]:
    """Adds ``apply_sorting``; subclasses implement ``get_sorting_clause``."""

    sorting_enum: type[PE]

    def apply_sorting(
        self,
        statement: Select[tuple[M]],
        sorting: Sequence[Sorting[PE]],
    ) -> Select[tuple[M]]:
        order_clauses = [
            (desc if is_descending else asc)(self.get_sorting_clause(criterion))
            for criterion, is_descending in sorting
        ]
        return statement.order_by(*order_clauses)

    def get_sorting_clause(self, property: PE) -> SortingClause:
        raise NotImplementedError()
