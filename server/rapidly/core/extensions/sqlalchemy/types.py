"""Custom SQLAlchemy column types for mapping Python enums to database columns.

Two flavours are provided:

* :class:`StringEnum` — stores ``enum.Enum`` members by their Unicode value.
* :class:`StrEnumType` — stores ``enum.StrEnum`` members as plain strings.
"""

from __future__ import annotations

from enum import Enum, StrEnum
from typing import TYPE_CHECKING, Any

import sqlalchemy as sa
from sqlalchemy.engine.interfaces import Dialect
from sqlalchemy.types import TypeDecorator as _TD

# Workaround for TypeDecorator generics which are not supported at
# runtime but useful for type-checkers.
if TYPE_CHECKING:  # pragma: no cover
    _BaseDecorator = _TD[Any]
else:
    _BaseDecorator = _TD


# ---------------------------------------------------------------------------
# Generic enum base
# ---------------------------------------------------------------------------


class _EnumColumn(_BaseDecorator):
    """Abstract base for TypeDecorators that persist Enum members."""

    _enum_cls: type[Enum]

    def __init__(self, enum_klass: type[Enum], **kw: Any) -> None:
        super().__init__(**kw)
        self._enum_cls = enum_klass

    # Forward: Python -> DB
    def process_bind_param(self, value: Any, dialect: Dialect) -> Any:
        if isinstance(value, self._enum_cls):
            return value.value
        return value

    # Reverse: DB -> Python
    def process_result_value(self, value: Any, dialect: Dialect) -> Any:
        if value is None:
            return None
        return self._enum_cls(value)


class StringEnum(_EnumColumn):
    """Persist an ``Enum`` as a Unicode text column."""

    impl = sa.Unicode
    cache_ok = True


# ---------------------------------------------------------------------------
# StrEnum-specific column type
# ---------------------------------------------------------------------------


class StrEnumType(_BaseDecorator):
    """Persist a ``StrEnum`` member as a plain ``VARCHAR`` / ``TEXT`` value."""

    impl = sa.String
    cache_ok = True

    _enum_cls: type[StrEnum]

    def __init__(self, enum_klass: type[StrEnum], **kw: Any) -> None:
        super().__init__(**kw)
        self._enum_cls = enum_klass

    def process_bind_param(self, value: Any, dialect: Dialect) -> Any:
        return str(value) if isinstance(value, self._enum_cls) else value

    def process_result_value(self, value: Any, dialect: Dialect) -> Any:
        return self._enum_cls(value) if value is not None else None
