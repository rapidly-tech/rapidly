"""Tests for ``rapidly/admin/components/_datatable.py``.

Pure helpers + Datatable container. Three load-bearing surfaces:

- ``SortWay`` enum (ASC / DESC). Drift to add a third state would
  break the icon-class mapping in ``_render_head``.
- ``Datatable.__init__`` empty_message default ("No items found").
  Drift would silently change the placeholder text on every
  empty list page.
- ``_current_sort_direction`` returns ASC / DESC / None based on
  the column's sorting key matching the current sort criteria.
  Drift would render the wrong sort indicator (admins click the
  arrow icon to toggle direction; wrong indicator → wrong toggle
  result).
"""

from __future__ import annotations

from enum import StrEnum

from rapidly.admin.components import _datatable as M
from rapidly.admin.components._datatable import (
    Datatable,
    DatatableSortingColumn,
    SortWay,
)


class _SortKey(StrEnum):
    name = "name"
    created = "created_at"


class TestSortWay:
    def test_two_directions(self) -> None:
        # Pin: ASC / DESC only. Drift to add a third state would
        # break the icon-class mapping in _render_head.
        assert {member.name for member in SortWay} == {"ASC", "DESC"}


class TestDatatableInit:
    def test_default_empty_message(self) -> None:
        # Pin: documented placeholder. Drift would change the
        # text on every empty list page.
        table: Datatable[object, _SortKey] = Datatable()
        assert table.empty_message == "No items found"

    def test_custom_empty_message(self) -> None:
        table: Datatable[object, _SortKey] = Datatable(empty_message="No customers")
        assert table.empty_message == "No customers"

    def test_columns_stored_in_order(self) -> None:
        col1: DatatableSortingColumn[object, _SortKey] = DatatableSortingColumn("Name")
        col2: DatatableSortingColumn[object, _SortKey] = DatatableSortingColumn(
            "Created"
        )
        table: Datatable[object, _SortKey] = Datatable(col1, col2)
        # Pin: tuple, NOT list (frozen ordering).
        assert table.columns == (col1, col2)


class TestCurrentSortDirection:
    def _table_with_col(
        self, sorting_key: _SortKey | None
    ) -> tuple[Datatable[object, _SortKey], DatatableSortingColumn[object, _SortKey]]:
        col: DatatableSortingColumn[object, _SortKey] = DatatableSortingColumn(
            "X", sorting=sorting_key
        )
        table: Datatable[object, _SortKey] = Datatable(col)
        return table, col

    def test_returns_none_when_sorting_list_is_none(self) -> None:
        # Pin: no active sort → None (column header shows label
        # only, no arrow).
        table, col = self._table_with_col(_SortKey.name)
        assert table._current_sort_direction(None, col) is None

    def test_returns_none_when_column_not_sortable(self) -> None:
        # Pin: a column without a sorting key never shows an arrow.
        table, col = self._table_with_col(None)
        assert table._current_sort_direction([], col) is None

    def test_returns_asc_for_ascending_field(self) -> None:
        # Pin: matching field with descending=False → ASC.
        table, col = self._table_with_col(_SortKey.name)
        result = table._current_sort_direction([(_SortKey.name, False)], col)
        assert result == SortWay.ASC

    def test_returns_desc_for_descending_field(self) -> None:
        # Pin: matching field with descending=True → DESC.
        table, col = self._table_with_col(_SortKey.name)
        result = table._current_sort_direction([(_SortKey.name, True)], col)
        assert result == SortWay.DESC

    def test_returns_none_when_no_match(self) -> None:
        # Pin: when the active sort is on a different field, this
        # column shows no arrow.
        table, col = self._table_with_col(_SortKey.name)
        result = table._current_sort_direction([(_SortKey.created, False)], col)
        assert result is None


class TestRepr:
    def test_repr_includes_columns_and_empty_message(self) -> None:
        # Pin: __repr__ format used in admin dev console.
        table: Datatable[object, _SortKey] = Datatable(empty_message="None yet")
        r = repr(table)
        assert "Datatable" in r
        assert "empty_message='None yet'" in r


class TestExports:
    def test_dunder_all_pinned(self) -> None:
        # Pin: documented public API of the datatable module.
        assert M.__all__ == [
            "Datatable",
            "DatatableActionsColumn",
            "DatatableAttrColumn",
            "DatatableColumn",
            "DatatableDateTimeColumn",
            "pagination",
        ]
