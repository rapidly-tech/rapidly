"""Key-value detail panels for admin entity views.

Provides typed column items (plain text, datetime, currency, link,
socials) and a ``DescriptionList`` container that renders them inside
a ``<dl>`` with consistent layout and formatting.
"""

import contextlib
from collections.abc import Callable, Generator
from datetime import datetime
from inspect import isgenerator
from operator import attrgetter
from typing import Any

from fastapi import Request
from fastapi.datastructures import URL
from tagflow import attr, classes, tag, text

from .. import formatters
from ._clipboard_button import clipboard_button

# ---------------------------------------------------------------------------
# Item hierarchy
# ---------------------------------------------------------------------------

# Maps lowercase platform names to display labels for social links.
_SOCIAL_LABELS: dict[str, str] = {
    "twitter": "\U0001d54f:",
    "x": "\U0001d54f:",
    "github": "GitHub:",
    "linkedin": "LinkedIn:",
    "youtube": "YouTube:",
    "instagram": "Instagram:",
    "facebook": "Facebook:",
    "discord": "Discord:",
}


class DescriptionListItem[M]:
    """Base class -- subclasses implement :meth:`render`."""

    label: str

    def __init__(self, label: str) -> None:
        self.label = label

    def render(self, request: Request, item: M) -> Generator[None] | None:
        raise NotImplementedError

    @contextlib.contextmanager
    def _do_render(self, request: Request, item: M) -> Generator[None]:
        result = self.render(request, item)
        if isgenerator(result):
            yield from result
        else:
            yield

    def __repr__(self) -> str:
        return f"{type(self).__name__}(label={self.label!r})"


class DescriptionListAttrItem[M](DescriptionListItem[M]):
    """Displays an object attribute as plain text, with optional clipboard."""

    attr: str
    clipboard: bool

    def __init__(
        self, attr: str, label: str | None = None, *, clipboard: bool = False
    ) -> None:
        self.attr = attr
        self.clipboard = clipboard
        super().__init__(label or attr)

    def get_raw_value(self, item: M) -> Any | None:
        return attrgetter(self.attr)(item)

    def get_value(self, item: M) -> str | None:
        raw = self.get_raw_value(item)
        return None if raw is None else str(raw)

    def render(self, request: Request, item: M) -> Generator[None] | None:
        display = self.get_value(item)
        with tag.div(classes="flex items-center gap-1"):
            text(display if display is not None else "\u2014")
            if display is not None and self.clipboard:
                with clipboard_button(display):
                    pass
        return None

    def __repr__(self) -> str:
        return (
            f"{type(self).__name__}(attr={self.attr!r}, "
            f"label={self.label!r}, clipboard={self.clipboard})"
        )


class DescriptionListDateTimeItem[M](DescriptionListAttrItem[M]):
    """Formats a ``datetime`` through the admin date formatter."""

    def get_value(self, item: M) -> str | None:
        raw: datetime | None = self.get_raw_value(item)
        return None if raw is None else formatters.datetime(raw)


class DescriptionListLinkItem[M](DescriptionListAttrItem[M]):
    """Renders the attribute as a clickable hyperlink."""

    href_getter: Callable[[Request, M], str | URL | None]

    def __init__(
        self,
        attr: str,
        label: str | None = None,
        *,
        external: bool = False,
        href_getter: Callable[[Request, M], str | URL | None] | None = None,
    ) -> None:
        super().__init__(attr, label, clipboard=False)
        self.external = external

        if href_getter is not None:
            self.href_getter = href_getter
        else:

            def _fallback(_req: Request, obj: M) -> str | URL | None:
                return self.get_raw_value(obj)

            self.href_getter = _fallback

    def render(self, request: Request, item: M) -> Generator[None] | None:
        raw = self.get_raw_value(item)
        href = self.href_getter(request, item)

        with tag.div(classes="flex items-center gap-1"):
            if raw is not None:
                with tag.a(href=href, classes="link"):
                    if self.external:
                        classes("flex flex-row gap-1")
                        attr("target", "_blank")
                        attr("rel", "noopener noreferrer")
                    text(str(raw))
                    if self.external:
                        with tag.div(classes="icon-external-link"):
                            pass
            else:
                text("\u2014")
        return None

    def __repr__(self) -> str:
        return (
            f"{type(self).__name__}(attr={self.attr!r}, "
            f"label={self.label!r}, external={self.external!r})"
        )


class DescriptionListSocialsItem[M](DescriptionListItem[M]):
    """Renders social-media links with platform labels and external icons."""

    def render(self, request: Request, item: M) -> Generator[None] | None:
        socials = getattr(item, "socials", []) or []
        twitter_handle = getattr(item, "twitter_username", None)

        with tag.div(classes="flex flex-col gap-2"):
            if twitter_handle:
                self._render_social_row(
                    label_text="\U0001d54f (Twitter):",
                    url=f"https://x.com/{twitter_handle}",
                    display=f"@{twitter_handle}",
                )

            for entry in socials:
                platform = entry.get("platform", "")
                url = entry.get("url", "")
                if not (platform and url):
                    continue

                label_text = _SOCIAL_LABELS.get(
                    platform.lower(), f"{platform.title()}:"
                )
                display = _strip_protocol(url)
                self._render_social_row(label_text=label_text, url=url, display=display)

            if not socials and not twitter_handle:
                with tag.span(classes="text-gray-500 italic"):
                    text("No social links available")

        return None

    @staticmethod
    def _render_social_row(label_text: str, url: str, display: str) -> None:
        with tag.div(classes="flex items-center gap-2"):
            with tag.span(classes="text-sm font-medium"):
                text(label_text)
            with tag.a(
                href=url,
                classes="link flex items-center gap-1",
                target="_blank",
                rel="noopener noreferrer",
            ):
                text(display)
                with tag.div(classes="icon-external-link"):
                    pass


def _strip_protocol(url: str) -> str:
    """Remove leading ``https://`` or ``http://`` for display."""
    for prefix in ("https://", "http://"):
        if url.startswith(prefix):
            return url[len(prefix) :]
    return url


# ---------------------------------------------------------------------------
# List container
# ---------------------------------------------------------------------------


class DescriptionList[M]:
    """Renders items as a ``<dl>`` with a three-column grid layout."""

    def __init__(self, *items: DescriptionListItem[M]) -> None:
        self.items = items

    @contextlib.contextmanager
    def render(self, request: Request, data: M) -> Generator[None]:
        with tag.dl(classes="divide-y divide-gray-100"):
            with tag.div(classes="px-4 py-6 sm:grid sm:grid-cols-3 sm:gap-4 sm:px-0"):
                for dl_item in self.items:
                    with tag.dt(classes="text-sm/6 font-medium"):
                        text(dl_item.label)
                        with tag.dd(classes="mt-1 text-sm/6 sm:col-span-2 sm:mt-0"):
                            with dl_item._do_render(request, data):
                                pass
        yield

    def __repr__(self) -> str:
        return f"{type(self).__name__}(items={self.items!r})"


__all__ = [
    "DescriptionList",
    "DescriptionListAttrItem",
    "DescriptionListDateTimeItem",
    "DescriptionListItem",
    "DescriptionListLinkItem",
]
