"""Tests for ``rapidly/catalog/share/ordering.py``."""

from __future__ import annotations

from rapidly.catalog.share.ordering import ShareSortProperty


class TestShareSortProperty:
    def test_exposes_documented_columns(self) -> None:
        assert {e.value for e in ShareSortProperty} == {
            "name",
            "created_at",
            "price_amount",
            "price_amount_type",
        }

    def test_product_name_attribute_alias(self) -> None:
        # StrEnum reserved-word workaround.
        assert ShareSortProperty.product_name.value == "name"

    def test_is_str_enum(self) -> None:
        assert str(ShareSortProperty.price_amount) == "price_amount"
