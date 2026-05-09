"""Tests for ``rapidly/core/types.py``.

The module supplies the base Pydantic schemas every API response inherits
from, plus the string-normalising validators and OpenAPI metadata
annotations that Rapidly relies on. None were covered.

Tests pin:
- Base-schema ORM-mode config (``from_attributes=True``)
- ``empty_str_to_none`` / ``_validate_slug`` validator semantics
- OpenAPI annotation dataclasses are hashable (Pydantic + Python
  ``Annotated`` metadata must be hashable to participate in type hashing)
- ``MultipleQueryFilter._scalar_to_sequence`` normalisation (scalar → [x],
  sequence stays a sequence, str stays wrapped as a single value)
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

import pytest
from pydantic import BaseModel, TypeAdapter, ValidationError

from rapidly.core.types import (
    CUSTOMER_ID_EXAMPLE,
    WORKSPACE_ID_EXAMPLE,
    AuditableSchema,
    ClassName,
    IdentifiableSchema,
    MergeJSONSchema,
    MultipleQueryFilter,
    Schema,
    SelectorWidget,
    SetSchemaReference,
    _validate_slug,
    empty_str_to_none,
)


class TestBaseSchemas:
    def test_schema_has_from_attributes_enabled(self) -> None:
        # ORM mode lets routes return SQLAlchemy objects directly.
        # A regression that flipped this off would break every list
        # endpoint returning ORM results.
        assert Schema.model_config.get("from_attributes") is True

    def test_identifiable_inherits_schema(self) -> None:
        assert issubclass(IdentifiableSchema, Schema)

    def test_identifiable_requires_uuid_id(self) -> None:
        with pytest.raises(ValidationError):
            IdentifiableSchema(id="not-a-uuid")  # type: ignore[arg-type]
        obj = IdentifiableSchema(id=WORKSPACE_ID_EXAMPLE)  # type: ignore[arg-type]
        assert isinstance(obj.id, UUID)

    def test_auditable_allows_nullable_modified_at(self) -> None:
        # ``modified_at`` is nullable on creation — ``created_at`` is
        # not. The distinction matters: freshly-created rows have no
        # modification timestamp.
        now = datetime.now(UTC)
        obj = AuditableSchema(created_at=now, modified_at=None)
        assert obj.modified_at is None
        with pytest.raises(ValidationError):
            AuditableSchema(modified_at=now)  # type: ignore[call-arg]


class TestEmptyStrToNone:
    def test_empty_string_becomes_none(self) -> None:
        assert empty_str_to_none("") is None

    def test_whitespace_only_becomes_none(self) -> None:
        # Important for form submissions where a field was emptied —
        # we must not persist "   " as a non-empty string.
        assert empty_str_to_none("   ") is None
        assert empty_str_to_none("\t\n") is None

    def test_surrounding_whitespace_is_stripped(self) -> None:
        assert empty_str_to_none("  alice  ") == "alice"

    def test_none_passes_through(self) -> None:
        assert empty_str_to_none(None) is None

    def test_non_string_passes_through(self) -> None:
        # Pydantic ``AfterValidator`` is called for the declared type
        # but the helper also short-circuits on non-str inputs — an
        # early ``isinstance`` check returns the value unchanged.
        from typing import Any, cast

        result: Any = empty_str_to_none(cast("str | None", 42))
        assert result == 42


class TestValidateSlug:
    @pytest.mark.parametrize("ok", ["alice", "alice-in-wonderland", "a1b2"])
    def test_accepts_canonical_slugs(self, ok: str) -> None:
        assert _validate_slug(ok) == ok

    @pytest.mark.parametrize(
        "hostile",
        [
            "Alice",  # uppercase
            "alice in wonderland",  # spaces
            "alice_underscore",  # underscore is not a hyphen
            "café",  # non-ASCII
            "alice!",  # punctuation
        ],
    )
    def test_rejects_non_canonical(self, hostile: str) -> None:
        with pytest.raises(ValueError, match="ASCII letters"):
            _validate_slug(hostile)


class TestOpenAPIAnnotationsAreHashable:
    # Pydantic's ``Annotated`` metadata must be hashable — Python
    # stores type annotations in ``__metadata__`` tuples that are hashed
    # for caching. A regression that removed ``__hash__`` would break
    # every model that uses these annotations.

    def test_classname_is_hashable(self) -> None:
        hash(ClassName("X"))

    def test_merge_json_schema_is_hashable(self) -> None:
        hash(MergeJSONSchema(json_schema={"title": "X"}))

    def test_set_schema_reference_is_hashable(self) -> None:
        hash(SetSchemaReference(ref_name="X"))

    def test_selector_widget_is_hashable(self) -> None:
        hash(
            SelectorWidget(
                resource_root="/x", resource_name="x", display_property="name"
            )
        )


class TestSelectorWidgetExtraAttributes:
    def test_emits_x_rapidly_selector_widget(self) -> None:
        # The JSON schema extra key is what the dashboard reads to
        # render a foreign-key selector. A rename here silently
        # breaks the dashboard UI.
        widget = SelectorWidget(
            resource_root="/v1/x", resource_name="X", display_property="name"
        )
        extras = widget._get_extra_attributes()
        assert extras == {
            "x-rapidly-selector-widget": {
                "resourceRoot": "/v1/x",
                "resourceName": "X",
                "displayProperty": "name",
            }
        }


class TestMultipleQueryFilter:
    # Pydantic constructs the filter via its core schema; exercise the
    # end-to-end normalisation through a TypeAdapter to cover the
    # ``_scalar_to_sequence`` hook under the same path the API uses.

    def test_scalar_is_wrapped_as_single_element(self) -> None:
        ta = TypeAdapter(MultipleQueryFilter[int])
        result = ta.validate_python(7)
        assert list(result) == [7]

    def test_sequence_passes_through(self) -> None:
        ta = TypeAdapter(MultipleQueryFilter[int])
        result = ta.validate_python([1, 2, 3])
        assert list(result) == [1, 2, 3]

    def test_string_is_wrapped_not_iterated(self) -> None:
        # Critical: a string is iterable but must NOT be broken into
        # characters. A regression that treated "abc" as ["a", "b",
        # "c"] would mangle every filter query.
        ta = TypeAdapter(MultipleQueryFilter[str])
        result = ta.validate_python("alice")
        assert list(result) == ["alice"]

    def test_requires_type_argument(self) -> None:
        with pytest.raises(TypeError):

            class _M(BaseModel):
                v: MultipleQueryFilter  # type: ignore[type-arg]


class TestExampleUUIDs:
    # These UUIDs are embedded in the generated OpenAPI / MDX / TS
    # client. Drifting them would break example requests in the
    # published docs without a visible failure.
    def test_workspace_id_is_valid_uuid4(self) -> None:
        u = UUID(WORKSPACE_ID_EXAMPLE)
        assert u.version == 4

    def test_customer_id_is_valid_uuid4(self) -> None:
        u = UUID(CUSTOMER_ID_EXAMPLE)
        assert u.version == 4

    def test_example_ids_are_distinct(self) -> None:
        assert WORKSPACE_ID_EXAMPLE != CUSTOMER_ID_EXAMPLE
