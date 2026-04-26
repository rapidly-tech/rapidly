"""Placeholder states and generic card container.

Provides visual feedback for empty data sets, loading spinners, and
a reusable bordered card wrapper.
"""

import contextlib
from collections.abc import Generator
from typing import Any

from tagflow import tag, text

_SPINNER_SIZES: dict[str, str] = {
    "xs": "loading-xs",
    "sm": "loading-sm",
    "md": "loading-md",
    "lg": "loading-lg",
}


@contextlib.contextmanager
def empty_state(
    title: str,
    description: str | None = None,
    icon: str | None = None,
    **kwargs: Any,
) -> Generator[None]:
    """Centred placeholder shown when a list or section has no data.

    The caller can yield action buttons (e.g. "Create first ...").
    """
    with tag.div(
        classes="flex flex-col items-center justify-center py-12 px-4 text-center",
        **kwargs,
    ):
        if icon:
            with tag.div(classes="text-6xl mb-4 opacity-50"):
                text(icon)
        with tag.h3(classes="text-xl font-bold mb-2"):
            text(title)
        if description:
            with tag.p(classes="text-base-content/70 mb-4 max-w-md"):
                text(description)
        yield


@contextlib.contextmanager
def loading_state(
    message: str = "Loading...",
    size: str = "md",
    **kwargs: Any,
) -> Generator[None]:
    """DaisyUI spinner with an optional text label."""
    spinner_cls = _SPINNER_SIZES.get(size, "loading-md")

    with tag.div(
        classes="flex flex-col items-center justify-center py-12 gap-4",
        role="status",
        **kwargs,
    ):
        with tag.span(classes=f"loading loading-spinner {spinner_cls}"):
            pass
        if message:
            with tag.p(classes="text-base-content/70"):
                text(message)
        yield


@contextlib.contextmanager
def card(
    *,
    bordered: bool = True,
    compact: bool = False,
    **kwargs: Any,
) -> Generator[None]:
    """Simple bordered card wrapper.

    Args:
        bordered: Draw a 1 px border.
        compact: Reduce internal padding from ``p-4`` to ``p-3``.
        **kwargs: Extra HTML attributes; a ``classes`` key is merged
            rather than replaced.
    """
    parts = ["card", "bg-base-100"]
    if bordered:
        parts.append("border border-base-300")
    parts.append("p-3" if compact else "p-4")

    extra_classes = kwargs.pop("classes", "")
    if extra_classes:
        parts.append(extra_classes)

    with tag.div(classes=" ".join(parts), **kwargs):
        yield


__all__ = ["card", "empty_state", "loading_state"]
