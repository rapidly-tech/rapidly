"""Extended tests for ``rapidly/core/metadata.py``.

Complements the existing ``test_metadata.py`` (MetadataInputMixin
input-validation only) with pins on the rest of the module's
contracts:

- Constants (``MAXIMUM_KEYS = 50``, key max 40, value max 500)
- ``MetadataValue`` accepts str / int / float / bool
- ``MetadataOutputMixin`` reads both ``user_metadata`` AND ``metadata``
  aliases — backward compatibility during the rename migration
- ``_parse_metadata_query`` extracts ``?metadata[key]=value`` pairs
  in deepObject style and preserves repeats (OR semantics)
- ``get_nested_metadata_value`` dot-path traversal with safe misses
- OpenAPI schema helpers produce the documented shapes
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

from starlette.datastructures import ImmutableMultiDict

from rapidly.core.metadata import (
    MAXIMUM_KEYS,
    MetadataInputMixin,
    MetadataOutputMixin,
    _parse_metadata_query,
    add_metadata_query_schema,
    get_metadata_query_openapi_schema,
    get_nested_metadata_value,
)


class MetadataInput(MetadataInputMixin): ...


class MetadataOutput(MetadataOutputMixin): ...


# ── Constants ──


class TestConstants:
    def test_maximum_keys_is_50(self) -> None:
        # Pin the documented limit — the API docstring + OpenAPI
        # description reference this number; drift would desync
        # them.
        assert MAXIMUM_KEYS == 50


# ── MetadataValue acceptance ──


class TestMetadataValueAcceptance:
    def test_string_value(self) -> None:
        MetadataInput(metadata={"k": "value"})

    def test_int_value(self) -> None:
        MetadataInput(metadata={"k": 42})

    def test_float_value(self) -> None:
        MetadataInput(metadata={"k": 1.5})

    def test_bool_value(self) -> None:
        MetadataInput(metadata={"k": True})


# ── MetadataOutputMixin alias choices ──


class TestMetadataOutputAliases:
    def test_reads_user_metadata_alias(self) -> None:
        # The ORM column is ``user_metadata`` — response schemas
        # deserialise that key into the public ``metadata`` field.
        body = MetadataOutput.model_validate({"user_metadata": {"k": "v"}})
        assert body.metadata == {"k": "v"}

    def test_reads_metadata_alias(self) -> None:
        # Backward-compat — older callers (pre-rename) may hand in
        # ``metadata`` directly. Pinning both aliases keeps the
        # transition window safe.
        body = MetadataOutput.model_validate({"metadata": {"k": "v"}})
        assert body.metadata == {"k": "v"}


# ── Query parsing (deepObject style) ──


def _req_with_query(pairs: list[tuple[str, str]]) -> Any:
    req = MagicMock()
    req.query_params = ImmutableMultiDict(pairs)
    return req


class TestParseMetadataQuery:
    def test_single_key_value(self) -> None:
        req = _req_with_query([("metadata[env]", "prod")])
        result = _parse_metadata_query(req)
        assert result == {"env": ["prod"]}

    def test_multiple_keys(self) -> None:
        req = _req_with_query([("metadata[env]", "prod"), ("metadata[region]", "eu")])
        result = _parse_metadata_query(req)
        assert result == {"env": ["prod"], "region": ["eu"]}

    def test_repeated_key_collects_all_values(self) -> None:
        # ``?metadata[env]=prod&metadata[env]=staging`` — multiple
        # values for the same key become an OR-filter in the
        # WHERE clause builder downstream. Pinning preservation
        # of all repeats prevents a regression that collapsed
        # duplicates to the first.
        req = _req_with_query([("metadata[env]", "prod"), ("metadata[env]", "staging")])
        result = _parse_metadata_query(req)
        assert result == {"env": ["prod", "staging"]}

    def test_ignores_non_metadata_params(self) -> None:
        # Other query params (``?page=1``) must not leak into the
        # filter dict — otherwise every paginated list would get
        # ``page=1`` as a metadata key-value filter.
        req = _req_with_query([("metadata[env]", "prod"), ("page", "1")])
        result = _parse_metadata_query(req)
        assert result == {"env": ["prod"]}

    def test_no_metadata_params_returns_empty_dict(self) -> None:
        req = _req_with_query([("page", "1")])
        result = _parse_metadata_query(req)
        assert result == {}


# ── Nested dot-path traversal ──


class TestGetNestedMetadataValue:
    def test_simple_key(self) -> None:
        assert get_nested_metadata_value({"a": 1}, "a") == 1

    def test_nested_path(self) -> None:
        assert get_nested_metadata_value({"a": {"b": 42}}, "a.b") == 42

    def test_three_level_path(self) -> None:
        assert get_nested_metadata_value({"a": {"b": {"c": "x"}}}, "a.b.c") == "x"

    def test_missing_segment_returns_none(self) -> None:
        # Dot-path into a key that doesn't exist must not raise —
        # callers expect None as the "miss" sentinel.
        assert get_nested_metadata_value({"a": {"b": 1}}, "a.c") is None

    def test_empty_path_returns_none(self) -> None:
        assert get_nested_metadata_value({"a": 1}, "") is None

    def test_traversal_stops_at_non_dict(self) -> None:
        # Walking into a leaf value must short-circuit, not
        # AttributeError. A regression that called ``.get(...)``
        # on a non-dict would crash every filter evaluation.
        assert get_nested_metadata_value({"a": 42}, "a.b") is None


# ── OpenAPI schema helpers ──


class TestOpenAPISchemaHelpers:
    def test_add_metadata_query_schema_injects_component(self) -> None:
        schema: dict[str, Any] = {"components": {"schemas": {}}}
        result = add_metadata_query_schema(schema)
        assert "MetadataQuery" in result["components"]["schemas"]

    def test_query_parameter_descriptor_uses_deepobject_style(self) -> None:
        # ``deepObject`` is what OpenAPI uses to describe
        # bracketed-key query params (``metadata[env]=prod``).
        # Clients rely on this style to generate the right URL.
        desc = get_metadata_query_openapi_schema()
        assert desc["style"] == "deepObject"
        assert desc["name"] == "metadata"
        assert desc["in"] == "query"
        assert desc["schema"] == {"$ref": "#/components/schemas/MetadataQuery"}
