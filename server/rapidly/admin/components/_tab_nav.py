"""Horizontal (or vertical) tab navigation for admin detail pages.

Each tab can carry a URL for link-based navigation, an optional count
badge, and an active-state flag.
"""

import contextlib
from collections.abc import Generator
from dataclasses import dataclass
from typing import Any

from tagflow import attr, tag, text


@dataclass(slots=True)
class Tab:
    """Descriptor for a single tab stop."""

    label: str
    url: str | None = None
    active: bool = False
    count: int | None = None
    badge_variant: str | None = None


def _render_tab_content(tab_def: Tab) -> None:
    """Emit the label text and optional count badge for a tab."""
    text(tab_def.label)
    if tab_def.count is not None:
        badge_cls = (
            f"badge-{tab_def.badge_variant}"
            if tab_def.badge_variant
            else "badge-neutral"
        )
        with tag.span(classes=f"badge {badge_cls} ml-2"):
            text(str(tab_def.count))


@contextlib.contextmanager
def tab_nav(
    tabs: list[Tab],
    *,
    vertical: bool = False,
    **kwargs: Any,
) -> Generator[None]:
    """Render a DaisyUI tab bar with bordered style.

    Args:
        tabs: Ordered list of :class:`Tab` descriptors.
        vertical: Stack tabs vertically instead of horizontally.
        **kwargs: Extra HTML attributes on the container.
    """
    orientation = "vertical" if vertical else "horizontal"
    base_classes = "tabs tabs-bordered"
    if vertical:
        base_classes += " flex-col"

    with tag.div(
        classes=base_classes,
        role="tablist",
        **kwargs,
    ):
        attr("aria-orientation", orientation)

        for tab_def in tabs:
            css = "tab tab-active" if tab_def.active else "tab"

            if tab_def.url:
                with tag.a(href=tab_def.url, classes=css, role="tab"):
                    if tab_def.active:
                        attr("aria-selected", "true")
                    _render_tab_content(tab_def)
            else:
                with tag.button(classes=css, role="tab", type="button"):
                    if tab_def.active:
                        attr("aria-selected", "true")
                    _render_tab_content(tab_def)

        yield


__all__ = ["Tab", "tab_nav"]
