"""Tests for ``rapidly/catalog/file/ordering.py``."""

from __future__ import annotations

from rapidly.catalog.file.ordering import FileSortProperty


class TestFileSortProperty:
    def test_exposes_created_at_and_name(self) -> None:
        assert {e.value for e in FileSortProperty} == {"created_at", "name"}

    def test_file_name_attribute_alias(self) -> None:
        # StrEnum reserved-word workaround: attribute is ``file_name``,
        # on-wire value is ``"name"`` (aligned with DB column).
        assert FileSortProperty.file_name.value == "name"

    def test_is_str_enum(self) -> None:
        assert str(FileSortProperty.created_at) == "created_at"
