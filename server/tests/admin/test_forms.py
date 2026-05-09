"""Tests for ``rapidly/admin/forms.py`` — pure helpers.

Five load-bearing surfaces:

- ``_collect_errors_for_field`` filters errors whose first loc
  segment matches the field name AND strips the leading segment
  so sub-field errors resolve against the nested form. Drift
  would either show all errors on every field (noisy) or hide
  sub-form errors (silent submission failure).
- ``_resolve_field_value`` returns the user's RAW input from the
  validation error (so they see what they typed) and only falls
  back to the data source when no error matches. Drift would
  blank out the field on validation failure (frustrating UX).
- ``_should_skip`` detects ``SkipField`` metadata as either the
  class itself OR an instance. Drift would let one form silently
  expose a field marked for skipping (potential PII leak).
- ``_widget_for_field`` picks widgets by type:
  * ``bool`` → CheckboxField
  * ``StrEnum`` → SelectField with member options
  * ``BaseForm`` subclass → SubFormField
  * default → InputField
  Explicit metadata takes priority. Drift would render the wrong
  widget for the type and break form submission.
- ``_parse_form_data`` un-flattens bracket-notated keys
  (``user[address][city]``) into nested dicts. Drift would
  silently drop nested form data (e.g., billing addresses).
- ``CurrencyValidator`` multiplies by 100 — converts dollars
  (display) to cents (storage). Drift would store dollars as
  cents (10000× under-charge) or vice-versa (10000× over-charge).
"""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Any

from fastapi.datastructures import FormData
from pydantic import BaseModel, Field

from rapidly.admin.forms import (
    BaseForm,
    CheckboxField,
    CurrencyValidator,
    InputField,
    SelectField,
    SkipField,
    SubFormField,
    _collect_errors_for_field,
    _parse_form_data,
    _resolve_field_value,
    _should_skip,
    _widget_for_field,
)


class TestCollectErrorsForField:
    def test_filters_by_first_loc_segment(self) -> None:
        errors: list[Any] = [
            {"loc": ("name",), "msg": "x", "input": "?"},
            {"loc": ("email",), "msg": "y", "input": "?"},
            {"loc": ("name", "first"), "msg": "z", "input": "?"},
        ]
        result = _collect_errors_for_field(errors, "name")
        assert len(result) == 2
        # Pin: leading segment STRIPPED so sub-field errors
        # resolve against the nested form.
        locs = [r["loc"] for r in result]
        assert () in locs
        assert ("first",) in locs

    def test_no_match_returns_empty(self) -> None:
        errors: list[Any] = [{"loc": ("other",), "msg": "x", "input": "?"}]
        assert _collect_errors_for_field(errors, "name") == []


class TestResolveFieldValue:
    def test_error_input_takes_precedence(self) -> None:
        # Pin (UX): on validation failure, the user sees what they
        # TYPED (NOT the previous saved value). Drift would blank
        # out the field on every failed submit.
        errors: list[Any] = [{"loc": ("name",), "msg": "x", "input": "raw-typed"}]
        # Source has a different value but error input wins.
        result = _resolve_field_value({"name": "saved"}, errors, "name")
        assert result == "raw-typed"

    def test_falls_back_to_dict_source(self) -> None:
        result = _resolve_field_value({"name": "saved"}, [], "name")
        assert result == "saved"

    def test_falls_back_to_attr_source(self) -> None:
        class _Obj:
            name = "obj-name"

        result = _resolve_field_value(_Obj(), [], "name")
        assert result == "obj-name"

    def test_returns_none_when_no_source(self) -> None:
        assert _resolve_field_value(None, [], "name") is None

    def test_only_strips_loc_when_directly_at_field_level(self) -> None:
        # Pin: the error.input replaces the value only when the
        # error's loc strips down to () — i.e., the error is
        # ABOUT this field, not a nested sub-field. Drift would
        # let a sub-field error blank out the parent.
        errors: list[Any] = [{"loc": ("name", "first"), "msg": "x", "input": "raw"}]
        # Sub-field error → fall back to source (not raw input).
        result = _resolve_field_value({"name": "saved"}, errors, "name")
        assert result == "saved"


class TestShouldSkip:
    def test_skip_field_class_metadata(self) -> None:
        # Pin: bare class reference works.
        class _Form(BaseModel):
            secret: Annotated[str, SkipField] = ""

        assert _should_skip(_Form.model_fields["secret"]) is True

    def test_skip_field_instance_metadata(self) -> None:
        # Pin: instance also works (typical Annotated[..., SkipField()]).
        class _Form(BaseModel):
            secret: Annotated[str, SkipField()] = ""

        assert _should_skip(_Form.model_fields["secret"]) is True

    def test_no_skip_metadata(self) -> None:
        class _Form(BaseModel):
            visible: str = ""

        assert _should_skip(_Form.model_fields["visible"]) is False


class _Color(StrEnum):
    red = "red"
    green = "green"


class _Sub(BaseForm):
    name: str = ""


class TestWidgetForField:
    def test_explicit_metadata_takes_priority(self) -> None:
        # Pin: metadata-declared widget wins over type-based
        # detection.
        explicit = InputField(type="email")

        class _Form(BaseModel):
            email: Annotated[str, explicit] = ""

        widget = _widget_for_field(_Form.model_fields["email"])
        assert widget is explicit

    def test_bool_yields_checkbox(self) -> None:
        class _Form(BaseModel):
            on: bool = False

        assert isinstance(_widget_for_field(_Form.model_fields["on"]), CheckboxField)

    def test_strenum_yields_select(self) -> None:
        class _Form(BaseModel):
            color: _Color = _Color.red

        widget = _widget_for_field(_Form.model_fields["color"])
        assert isinstance(widget, SelectField)
        # Pin: options carry (value, name) for each member.
        assert widget.options == [("red", "red"), ("green", "green")]

    def test_baseform_subclass_yields_subform(self) -> None:
        class _Form(BaseModel):
            sub: _Sub = Field(default_factory=_Sub)

        widget = _widget_for_field(_Form.model_fields["sub"])
        assert isinstance(widget, SubFormField)
        assert widget.form_class is _Sub

    def test_default_yields_input_field(self) -> None:
        class _Form(BaseModel):
            name: str = ""

        widget = _widget_for_field(_Form.model_fields["name"])
        assert isinstance(widget, InputField)
        # Default type is "text".
        assert widget.type == "text"


class TestParseFormData:
    def test_flat_keys_passthrough(self) -> None:
        data = FormData([("name", "Alice"), ("email", "a@b.com")])
        result = _parse_form_data(data)
        assert result == {"name": "Alice", "email": "a@b.com"}

    def test_bracket_notation_nests(self) -> None:
        # Pin: ``user[name]`` → ``{"user": {"name": ...}}``.
        data = FormData([("user[name]", "Alice"), ("user[email]", "a@b.com")])
        result = _parse_form_data(data)
        assert result == {
            "user": {"name": "Alice", "email": "a@b.com"},
        }

    def test_deep_nesting(self) -> None:
        # Pin: arbitrary depth (``user[address][city]`` →
        # 3-level nested dict).
        data = FormData(
            [
                ("user[address][city]", "NYC"),
                ("user[address][zip]", "10001"),
                ("user[name]", "Alice"),
            ]
        )
        result = _parse_form_data(data)
        assert result == {
            "user": {
                "name": "Alice",
                "address": {"city": "NYC", "zip": "10001"},
            }
        }

    def test_empty_form(self) -> None:
        assert _parse_form_data(FormData([])) == {}


class TestCurrencyValidator:
    def test_multiplies_by_100(self) -> None:
        # Pin: dollars (display) → cents (storage). Drift would
        # store dollars as cents (10000× under-charge) or
        # vice-versa.
        # CurrencyValidator wraps a lambda — reach into its func.
        assert CurrencyValidator.func(12.50) == 1250.0  # type: ignore[call-arg]

    def test_zero(self) -> None:
        assert CurrencyValidator.func(0) == 0  # type: ignore[call-arg]

    def test_integer_dollars(self) -> None:
        assert CurrencyValidator.func(100) == 10000  # type: ignore[call-arg]
