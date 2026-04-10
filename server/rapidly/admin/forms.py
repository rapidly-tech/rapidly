"""Server-rendered HTML form generation for the Rapidly admin panel.

Bridges Pydantic model definitions to DaisyUI-styled form controls.
Handles nested form data parsing, field-level validation error display,
and automatic widget selection based on field type annotations.
"""

import contextlib
import re
from collections.abc import Generator
from enum import StrEnum
from inspect import isclass
from typing import Any, Self

from fastapi.datastructures import FormData
from pydantic import AfterValidator, BaseModel, ValidationError
from pydantic.fields import FieldInfo
from pydantic_core import ErrorDetails
from tagflow import classes, tag, text
from tagflow.tagflow import AttrValue

type Data = dict[str, Any] | object

# ---------------------------------------------------------------------------
# Internal helpers for extracting field data and validation errors
# ---------------------------------------------------------------------------


def _collect_errors_for_field(
    all_errors: list[ErrorDetails], field_name: str
) -> list[ErrorDetails]:
    """Return only those errors whose first location segment matches *field_name*,
    with the leading segment stripped so sub-fields resolve correctly."""
    return [
        {**err, "loc": err["loc"][1:]}
        for err in all_errors
        if err["loc"][0] == field_name
    ]


def _resolve_field_value(
    source: Data | None,
    all_errors: list[ErrorDetails],
    field_name: str,
) -> Any | None:
    """Determine the current value for a form field.

    Prefers the raw input captured alongside a validation error (so the
    user sees what they typed), falling back to the supplied data source.
    """
    matching = _collect_errors_for_field(all_errors, field_name)
    for err in matching:
        if not err["loc"]:
            return err["input"]

    if source is None:
        return None
    if isinstance(source, dict):
        return source.get(field_name)
    return getattr(source, field_name, None)


# ---------------------------------------------------------------------------
# Widget protocol and sentinel for skipped fields
# ---------------------------------------------------------------------------


class FormField:
    """Abstract widget that knows how to render itself inside a ``<form>``.

    Concrete subclasses override :meth:`render` to emit DaisyUI-styled
    HTML via *tagflow* context managers.
    """

    @contextlib.contextmanager
    def render(
        self,
        id: str,
        label: str,
        *,
        required: bool = False,
        value: Any | None = None,
        errors: list[ErrorDetails] = [],
    ) -> Generator[None]:
        raise NotImplementedError


class SkipField:
    """Attach as Pydantic field metadata to exclude a field from auto-rendering.

    Usage::

        class MyForm(BaseForm):
            visible: str
            hidden: Annotated[str, SkipField()]
    """

    ...


# ---------------------------------------------------------------------------
# Concrete widget implementations
# ---------------------------------------------------------------------------


def _render_required_marker() -> None:
    """Emit a red asterisk next to the label text."""
    with tag.span(classes="text-error"):
        text("*")


def _render_validation_messages(errors: list[ErrorDetails]) -> None:
    """Emit error messages below a form control."""
    for err in errors:
        with tag.div(classes="label text-error"):
            text(err["msg"])


class InputField(FormField):
    """Standard ``<input>`` element supporting any HTML input *type*."""

    def __init__(self, type: str = "text", **kwargs: Any) -> None:
        self.type = type
        self.kwargs = kwargs

    @contextlib.contextmanager
    def render(
        self,
        id: str,
        label: str,
        *,
        required: bool = False,
        value: Any | None = None,
        errors: list[ErrorDetails] = [],
    ) -> Generator[None]:
        with tag.label(classes="label", **{"for": id}):
            text(label)
            if required:
                _render_required_marker()

        with tag.input(
            classes="input w-full",
            id=id,
            name=id,
            type=self.type,
            required=required,
            value=str(value) if value is not None else "",
            **self.kwargs,
        ):
            if errors:
                classes("input-error")

        _render_validation_messages(errors)
        yield


class TextAreaField(FormField):
    """Multi-line ``<textarea>`` with configurable row count."""

    def __init__(self, rows: int = 3, **kwargs: Any) -> None:
        self.rows = rows
        self.kwargs = kwargs

    @contextlib.contextmanager
    def render(
        self,
        id: str,
        label: str,
        *,
        required: bool = False,
        value: Any | None = None,
        errors: list[ErrorDetails] = [],
    ) -> Generator[None]:
        with tag.label(classes="label", **{"for": id}):
            text(label)
            if required:
                _render_required_marker()

        with tag.textarea(
            id=id,
            name=id,
            required=required,
            rows=self.rows,
            classes="textarea w-full",
            **self.kwargs,
        ):
            if errors:
                classes("textarea-error")
            if value is not None:
                text(str(value))

        _render_validation_messages(errors)
        yield


class CheckboxField(FormField):
    """Boolean toggle rendered as a DaisyUI checkbox."""

    def __init__(self, **kwargs: Any) -> None:
        self.kwargs = kwargs

    @contextlib.contextmanager
    def render(
        self,
        id: str,
        label: str,
        *,
        required: bool = False,
        value: Any | None = None,
        errors: list[ErrorDetails] = [],
    ) -> Generator[None]:
        with tag.label(classes="label", **{"for": id}):
            with tag.input(
                id=id,
                name=id,
                type="checkbox",
                required=required,
                checked=value,
                classes="checkbox",
                **self.kwargs,
            ):
                pass
            text(label)

        _render_validation_messages(errors)
        yield


class CurrencyField(InputField):
    """Numeric input that converts between cent storage and decimal display.

    Stored value ``1250`` (cents) is shown as ``12.50`` to the user.
    """

    def __init__(self, **kwargs: Any) -> None:
        super().__init__("number", **kwargs)

    @contextlib.contextmanager
    def render(
        self,
        id: str,
        label: str,
        *,
        required: bool = False,
        value: int | None = None,
        errors: list[ErrorDetails] = [],
    ) -> Generator[None]:
        display_value = value / 100 if value is not None else None
        with super().render(
            id,
            label,
            required=required,
            value=display_value,
            errors=errors,
        ):
            pass
        yield


class SelectField(FormField):
    """``<select>`` dropdown with ``(value, label)`` option pairs."""

    def __init__(
        self,
        options: list[tuple[str, str]],
        placeholder: str = "Select an option",
        **kwargs: Any,
    ) -> None:
        self.options = options
        self.placeholder = placeholder
        self.kwargs = kwargs

    @contextlib.contextmanager
    def render(
        self,
        id: str,
        label: str,
        *,
        required: bool = False,
        value: str | None = None,
        errors: list[ErrorDetails] = [],
    ) -> Generator[None]:
        with tag.legend(classes="label", **{"for": id}):
            text(label)
            if required:
                _render_required_marker()

        with tag.select(
            classes="select w-full",
            id=id,
            name=id,
            required=required,
            **self.kwargs,
        ):
            with tag.option(value="", selected=value is None):
                text(self.placeholder)
            for opt_val, opt_label in self.options:
                is_selected = (value == opt_val) if value is not None else False
                with tag.option(value=opt_val, selected=is_selected):
                    text(opt_label)

        _render_validation_messages(errors)
        yield


class SubFormField(FormField):
    """Embeds another :class:`BaseForm` inline as a grouped fieldset."""

    def __init__(self, form_class: type["BaseForm"]) -> None:
        self.form_class = form_class

    @contextlib.contextmanager
    def render(
        self,
        id: str,
        label: str,
        *,
        required: bool = False,
        value: Any | None = None,
        errors: list[ErrorDetails] = [],
    ) -> Generator[None]:
        with tag.fieldset(classes="fieldset border-base-300 rounded-box border p-4"):
            with tag.legend(classes="fieldset-legend"):
                text(label)

            for key, field_info in self.form_class.model_fields.items():
                if _should_skip(field_info):
                    continue
                widget = _widget_for_field(field_info)
                nested_id = f"{id}[{key}]"
                with widget.render(
                    nested_id,
                    field_info.title or key,
                    required=field_info.is_required(),
                    value=_resolve_field_value(value, errors, key),
                    errors=_collect_errors_for_field(errors, key),
                ):
                    pass
        yield


# ---------------------------------------------------------------------------
# Field introspection helpers
# ---------------------------------------------------------------------------


def _should_skip(field: FieldInfo) -> bool:
    """Return True when the field is tagged with :class:`SkipField`."""
    return any(m is SkipField or isinstance(m, SkipField) for m in field.metadata)


def _widget_for_field(field: FieldInfo) -> FormField:
    """Pick the right widget for *field* based on metadata and type annotation."""
    # Explicit widget attached via Annotated metadata takes priority.
    for m in field.metadata:
        if isinstance(m, FormField):
            return m

    annotation = field.annotation
    if annotation is not None:
        if annotation is bool:
            return CheckboxField()
        if isclass(annotation):
            if issubclass(annotation, BaseForm):
                return SubFormField(annotation)
            if issubclass(annotation, StrEnum):
                return SelectField(
                    options=[(member.value, member.name) for member in annotation]
                )

    return InputField()


# ---------------------------------------------------------------------------
# Pydantic validator for cent-based currency fields
# ---------------------------------------------------------------------------

CurrencyValidator = AfterValidator(lambda v: v * 100)


# ---------------------------------------------------------------------------
# Bracket-notation form-data parser  (user[address][city] -> nested dict)
# ---------------------------------------------------------------------------

_BRACKET_RE = re.compile(r"[^\[\]]+")


def _parse_form_data(raw: FormData) -> dict[str, Any]:
    """Unflatten bracket-notated form keys into a nested dict."""
    tree: dict[str, Any] = {}
    for raw_key, raw_val in raw.items():
        segments = _BRACKET_RE.findall(raw_key)
        node = tree
        for seg in segments[:-1]:
            node = node.setdefault(seg, {})
        node[segments[-1]] = raw_val
    return tree


# ---------------------------------------------------------------------------
# BaseForm -- Pydantic model that renders itself as an HTML <form>
# ---------------------------------------------------------------------------


class BaseForm(BaseModel):
    """Pydantic model that doubles as a self-rendering HTML form.

    Declare fields the normal Pydantic way; ``BaseForm`` will iterate
    them, pick matching widgets, and emit a DaisyUI ``<form>`` with
    inline validation errors.

    Two main entry points:

    * :meth:`render` -- context manager that writes the HTML.
    * :meth:`model_validate_form` -- parses ``FormData`` into the model,
      handling bracket-notated nested keys.

    Example::

        class EditProfileForm(BaseForm):
            display_name: str
            bio: Annotated[str, TextAreaField(rows=5)]

        # In the handler:
        with EditProfileForm.render(data=current_values, validation_error=err):
            with tag.button(type="submit"):
                text("Save")
    """

    @classmethod
    @contextlib.contextmanager
    def render(
        cls,
        data: Data | None = None,
        validation_error: ValidationError | None = None,
        **kwargs: AttrValue,
    ) -> Generator[None]:
        """Emit an HTML ``<form>`` containing all declared model fields.

        Fields marked with :class:`SkipField` are omitted.  Validation errors
        from a prior submission attempt are rendered inline next to the
        relevant controls.

        Args:
            data: Pre-fill values -- dict or object with matching attrs.
            validation_error: A :class:`~pydantic.ValidationError` from
                a prior form submission that failed validation.
            **kwargs: Forwarded as HTML attributes on the ``<form>`` tag
                (e.g. ``method``, ``action``, ``hx_post``).
        """
        err_list = validation_error.errors() if validation_error else []

        with tag.form(**kwargs, novalidate=True):
            with tag.fieldset(classes="fieldset"):
                for field_name, field_info in cls.model_fields.items():
                    if _should_skip(field_info):
                        continue

                    widget = _widget_for_field(field_info)
                    with widget.render(
                        field_name,
                        field_info.title or field_name,
                        required=field_info.is_required(),
                        value=_resolve_field_value(data, err_list, field_name),
                        errors=_collect_errors_for_field(err_list, field_name),
                    ):
                        pass
                yield

    @classmethod
    def model_validate_form(
        cls,
        obj: FormData,
        *,
        strict: bool | None = None,
        from_attributes: bool | None = None,
        context: Any | None = None,
        by_alias: bool | None = None,
        by_name: bool | None = None,
    ) -> Self:
        """Parse ``FormData`` (including bracket-notated keys) into this model."""
        return cls.model_validate(
            _parse_form_data(obj),
            strict=strict,
            from_attributes=from_attributes,
            context=context,
            by_alias=by_alias,
            by_name=by_name,
        )
