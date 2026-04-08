"""Dashboard statistic cards for the admin panel.

Renders a compact card showing a labelled metric value with optional
trend arrow and subtitle.
"""

import contextlib
from collections.abc import Generator
from typing import Any, Literal

from tagflow import tag, text

Variant = Literal["default", "success", "warning", "error", "info"]

_TREND_SYMBOLS: dict[str, str] = {
    "up": "\u2197",  # north-east arrow
    "down": "\u2198",  # south-east arrow
    "neutral": "\u2192",  # right arrow
}

_TREND_COLORS: dict[str, str] = {
    "up": "text-base-content/60",
    "down": "text-base-content/60",
    "neutral": "text-base-content/50",
}


@contextlib.contextmanager
def metric_card(
    label: str,
    value: str | int | float,
    *,
    variant: Variant = "default",
    subtitle: str | None = None,
    trend: Literal["up", "down", "neutral"] | None = None,
    compact: bool = False,
    **kwargs: Any,
) -> Generator[None]:
    """Render a single KPI card.

    Args:
        label: Short description of the metric (shown in uppercase).
        value: The headline number or string.
        variant: Not currently differentiated visually -- reserved
            for future per-variant border colours.
        subtitle: Secondary text below the value.
        trend: Directional arrow indicator.
        compact: Use tighter padding and smaller text.
        **kwargs: Extra HTML attributes for the outer card ``<div>``.
    """
    pad = "p-3" if compact else "p-4"
    value_size = "text-xl" if compact else "text-3xl"

    with tag.div(classes=f"card border {pad} border-base-300", **kwargs):
        with tag.div(classes="flex flex-col gap-1"):
            with tag.div(
                classes="text-xs uppercase font-semibold text-base-content/60"
            ):
                text(label)

            with tag.div(classes="flex items-baseline gap-2"):
                with tag.div(classes=f"{value_size} font-bold font-mono"):
                    text(str(value))
                if trend is not None:
                    with tag.span(classes=f"text-lg {_TREND_COLORS[trend]}"):
                        text(_TREND_SYMBOLS[trend])

            if subtitle:
                with tag.div(classes="text-sm text-base-content/70"):
                    text(subtitle)

            yield


__all__ = ["Variant", "metric_card"]
