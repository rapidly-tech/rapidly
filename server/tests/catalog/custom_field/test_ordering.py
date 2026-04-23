"""Tests for ``rapidly/catalog/custom_field/ordering.py``."""

from __future__ import annotations

from rapidly.catalog.custom_field.ordering import CustomFieldSortProperty


class TestCustomFieldSortProperty:
    def test_exposes_documented_columns(self) -> None:
        assert {e.value for e in CustomFieldSortProperty} == {
            "slug",
            "name",
            "type",
            "created_at",
        }

    def test_custom_field_name_attribute_alias(self) -> None:
        # StrEnum reserved-word workaround.
        assert CustomFieldSortProperty.custom_field_name.value == "name"

    def test_is_str_enum(self) -> None:
        assert str(CustomFieldSortProperty.type) == "type"
