"""Standalone form-control components for the admin panel.

These are used outside the auto-rendering ``BaseForm`` flow -- for
toolbar search bars, inline filters, and one-off select dropdowns.
"""

import contextlib
from collections.abc import Generator, Sequence

from tagflow import classes as _apply_classes
from tagflow import tag, text
from tagflow.tagflow import AttrValue


@contextlib.contextmanager
def search(
    name: str | None = None,
    value: str | None = None,
    placeholder: str | None = None,
) -> Generator[None]:
    """Render a search input with a magnifying-glass icon.

    The ``type="search"`` attribute enables the browser's native clear
    button on supporting platforms.
    """
    with tag.label(classes="input"):
        with tag.div(classes="icon-search opacity-50"):
            pass
        with tag.input(
            type="search",
            classes="grow",
            name=name,
            value=value,
            placeholder=placeholder,
        ):
            pass
    yield


@contextlib.contextmanager
def select(
    options: Sequence[tuple[str, str]],
    value: str | None = None,
    *,
    placeholder: str | None = None,
    classes: str | None = None,
    **kwargs: AttrValue,
) -> Generator[None]:
    """Render a ``<select>`` dropdown with DaisyUI styling.

    Args:
        options: ``(display_label, form_value)`` pairs.
        value: Currently selected value (matched against form values).
        placeholder: Optional default option with empty value.
        classes: Extra CSS classes appended to the ``<select>``.
        **kwargs: Additional HTML attributes (``name``, ``id``, etc.).
    """
    with tag.select(classes="select", **kwargs):
        if classes is not None:
            _apply_classes(classes)
        if placeholder is not None:
            with tag.option(value="", selected=not value):
                text(placeholder)
        for display_label, form_value in options:
            with tag.option(value=form_value, selected=form_value == value):
                text(display_label)
    yield


__all__ = ["search", "select"]
