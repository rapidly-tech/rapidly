"""Tests for ``rapidly/core/extensions/sqlalchemy/types.py``.

The custom TypeDecorator subclasses persist Python enum values to the
DB and hydrate them back on read. Two flavours share near-identical
semantics but differ in impl + storage:

- ``StringEnum`` stores ``Enum`` members by their Unicode ``.value``
- ``StrEnumType`` stores ``StrEnum`` members as plain VARCHAR/TEXT

Load-bearing pins:
- ``process_bind_param`` converts enum → value (write path); non-enum
  values pass through so callers can still write raw strings
- ``process_result_value`` reconstructs enum from the stored value
  (read path); None passes through unchanged
- ``cache_ok = True`` — SQLAlchemy requires this on custom
  TypeDecorators to cache compiled statements. A regression setting
  ``cache_ok = False`` would disable query caching for every column
  typed with these helpers (performance cliff on large tables)
- ``impl`` pinned (Unicode vs String) so a migration rename would
  surface here
"""

from __future__ import annotations

from enum import Enum, StrEnum
from unittest.mock import MagicMock

import sqlalchemy as sa

from rapidly.core.extensions.sqlalchemy.types import StrEnumType, StringEnum

# ── Fixtures (plain Python enums) ──


class Colour(Enum):
    red = "red"
    blue = "blue"
    green = "green"


class NumberStr(StrEnum):
    one = "one"
    two = "two"


# ── StringEnum ──


class TestStringEnum:
    def _col(self) -> StringEnum:
        return StringEnum(Colour)

    def test_impl_is_unicode(self) -> None:
        assert StringEnum.impl is sa.Unicode

    def test_cache_ok_true(self) -> None:
        # SQLAlchemy warns if cache_ok is unset; False would disable
        # statement caching on every column using this type.
        assert StringEnum.cache_ok is True

    def test_bind_converts_enum_to_value(self) -> None:
        col = self._col()
        assert col.process_bind_param(Colour.red, dialect=MagicMock()) == "red"

    def test_bind_passes_raw_value_through(self) -> None:
        # Non-enum writes (legacy rows, direct SQL) flow through
        # unchanged — a regression rejecting them would break
        # migrations that backfill string defaults.
        col = self._col()
        assert col.process_bind_param("red", dialect=MagicMock()) == "red"

    def test_bind_passes_none_through(self) -> None:
        col = self._col()
        assert col.process_bind_param(None, dialect=MagicMock()) is None

    def test_result_reconstructs_enum_member(self) -> None:
        col = self._col()
        assert col.process_result_value("blue", dialect=MagicMock()) is Colour.blue

    def test_result_none_stays_none(self) -> None:
        # Nullable columns must not raise on NULL rows.
        col = self._col()
        assert col.process_result_value(None, dialect=MagicMock()) is None


# ── StrEnumType ──


class TestStrEnumType:
    def _col(self) -> StrEnumType:
        return StrEnumType(NumberStr)

    def test_impl_is_string(self) -> None:
        # ``String`` (not ``Unicode``) — StrEnum values are ASCII
        # identifiers by convention, so the narrower type saves
        # bytes on Postgres.
        assert StrEnumType.impl is sa.String

    def test_cache_ok_true(self) -> None:
        assert StrEnumType.cache_ok is True

    def test_bind_converts_strenum_to_str(self) -> None:
        col = self._col()
        assert col.process_bind_param(NumberStr.one, dialect=MagicMock()) == "one"

    def test_bind_non_strenum_passes_through(self) -> None:
        # The isinstance guard lets a raw string flow through (for
        # legacy rows / direct SQL). A regression that coerced
        # via ``str(value)`` unconditionally would turn ints into
        # their decimal representation silently.
        col = self._col()
        assert col.process_bind_param("one", dialect=MagicMock()) == "one"

    def test_result_reconstructs_strenum(self) -> None:
        col = self._col()
        assert col.process_result_value("two", dialect=MagicMock()) is NumberStr.two

    def test_result_none_stays_none(self) -> None:
        col = self._col()
        assert col.process_result_value(None, dialect=MagicMock()) is None

    def test_unknown_value_raises(self) -> None:
        # A value that isn't in the enum must NOT be silently
        # coerced — ``StrEnum("garbage")`` raises ValueError.
        import pytest

        col = self._col()
        with pytest.raises(ValueError, match="not a valid"):
            col.process_result_value("garbage", dialect=MagicMock())


# ── Distinct type instances per enum ──


class TestDistinctInstances:
    def test_different_enums_yield_different_column_types(self) -> None:
        # Each ``StringEnum(MyEnum)`` is a distinct TypeDecorator
        # instance bound to a specific enum — the ORM relies on
        # this so two columns typed with different enums don't
        # share a cached bind-param path.
        a = StringEnum(Colour)
        b = StringEnum(NumberStr)
        assert a._enum_cls is Colour
        assert b._enum_cls is NumberStr
