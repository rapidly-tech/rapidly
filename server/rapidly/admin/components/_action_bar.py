"""Flexible action-bar container for grouping toolbar buttons.

Provides consistent spacing, alignment, and direction for sets of
action buttons used in detail headers, card footers, and form actions.
"""

import contextlib
from collections.abc import Generator
from typing import Any, Literal

from tagflow import tag

Position = Literal["left", "center", "right", "between"]

_JUSTIFY_MAP: dict[str, str] = {
    "left": "justify-start",
    "center": "justify-center",
    "right": "justify-end",
    "between": "justify-between",
}


@contextlib.contextmanager
def action_bar(
    *,
    position: Position = "right",
    vertical: bool = False,
    **kwargs: Any,
) -> Generator[None]:
    """Render a flex container that lays out child action elements.

    Args:
        position: How children are distributed along the main axis.
        vertical: Stack children top-to-bottom instead of left-to-right.
        **kwargs: Extra HTML attributes forwarded to the wrapper ``<div>``.
    """
    direction = "flex-col" if vertical else "flex-row"
    gap = "gap-3" if vertical else "gap-2"
    justify = _JUSTIFY_MAP[position]

    with tag.div(
        classes=f"flex {direction} items-center {gap} {justify}",
        **kwargs,
    ):
        yield


__all__ = ["Position", "action_bar"]
