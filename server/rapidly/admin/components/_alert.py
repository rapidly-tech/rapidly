"""Dismissible alert banners for the admin panel (DaisyUI ``alert``).

Supports ``info``, ``success``, ``warning``, and ``error`` colour
variants, plus the ``dash`` and ``soft`` DaisyUI modifiers.
"""

import contextlib
from collections.abc import Generator
from typing import Any

from sqlalchemy.util.typing import Literal
from tagflow import classes as _apply_classes
from tagflow import tag

Variant = Literal["info", "success", "warning", "error"]

_VARIANT_CLASS: dict[str, str] = {
    "info": "alert-info",
    "success": "alert-success",
    "warning": "alert-warning",
    "error": "alert-error",
}


@contextlib.contextmanager
def alert(
    variant: Variant | None = None,
    dash: bool = False,
    soft: bool = False,
    *,
    classes: str | None = None,
    **kwargs: Any,
) -> Generator[None]:
    """Render a DaisyUI alert banner with an ARIA ``role="alert"``.

    Args:
        variant: Semantic colour; omit for the neutral default.
        dash: Apply ``alert-dash`` modifier.
        soft: Apply ``alert-soft`` modifier.
        classes: Additional CSS class string to append.
        **kwargs: Forwarded to the outer ``<div>``.
    """
    with tag.div(classes="alert", role="alert", **kwargs):
        if variant is not None:
            _apply_classes(_VARIANT_CLASS[variant])
        if dash:
            _apply_classes("alert-dash")
        if soft:
            _apply_classes("alert-soft")
        if classes:
            _apply_classes(classes)
        yield


__all__ = ["Variant"]
