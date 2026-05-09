"""DaisyUI button component with colour, size, and style variants.

All parameters are keyword-only to keep call sites self-documenting.
"""

import contextlib
from collections.abc import Generator
from typing import Literal

from tagflow import classes, tag
from tagflow.tagflow import AttrValue

Variant = Literal[
    "neutral",
    "primary",
    "secondary",
    "accent",
    "info",
    "success",
    "warning",
    "error",
]
Size = Literal["xs", "sm", "md", "lg", "xl"]

_VARIANT_CLASS = {
    v: f"btn-{v}"
    for v in (
        "neutral",
        "primary",
        "secondary",
        "accent",
        "info",
        "success",
        "warning",
        "error",
    )
}
_SIZE_CLASS = {s: f"btn-{s}" for s in ("xs", "sm", "md", "lg", "xl")}


@contextlib.contextmanager
def button(
    *,
    variant: Variant | None = None,
    size: Size | None = None,
    ghost: bool = False,
    link: bool = False,
    soft: bool = False,
    outline: bool = False,
    **kwargs: AttrValue,
) -> Generator[None]:
    """Render a ``<button>`` with DaisyUI styling.

    Args:
        variant: Semantic colour (``"primary"``, ``"error"``, etc.).
        size: Button scale from ``"xs"`` to ``"xl"``.
        ghost: Transparent background, text-coloured.
        link: Styled as an inline hyperlink.
        soft: Muted / pastel background.
        outline: Transparent fill with a coloured border.
        **kwargs: Extra HTML attributes (``type``, ``hx_post``, etc.).
    """
    with tag.button(classes="btn", **kwargs):
        if variant:
            classes(_VARIANT_CLASS[variant])
        if size:
            classes(_SIZE_CLASS[size])
        for flag, css in (
            (ghost, "btn-ghost"),
            (link, "btn-link"),
            (soft, "btn-soft"),
            (outline, "btn-outline"),
        ):
            if flag:
                classes(css)
        yield


__all__ = ["button"]
