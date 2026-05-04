"""Tests for custom field data models."""

from rapidly.catalog.custom_field.data import custom_field_data_models


def test_custom_field_data_models() -> None:
    for model in custom_field_data_models:
        assert hasattr(model, "workspace"), (
            f"{model} should have an workspace property "
            "so we can update custom fields properly"
        )
