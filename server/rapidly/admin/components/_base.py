"""HTML document shell and page-title helper for admin panel pages.

Provides the ``<html>`` skeleton (head, body, meta tags, scripts,
global Hyperscript behaviours) and the OOB-swappable ``<title>`` tag.
"""

import contextlib
from collections.abc import Generator, Sequence

from fastapi import Request
from tagflow import tag, text

from ..static_urls import static_url

_TITLE_SUFFIX = "Rapidly Admin panel"

# Hyperscript behaviours injected into every page:
#   1. Auto-disable submit buttons while HTMX requests are in flight.
#   2. CopyToClipboard: copy text, toggle icon, re-enable after 5 s.
_GLOBAL_HYPERSCRIPT = """
on every htmx:beforeSend from <form />
    for submitButton in <button[type='submit'] /> in it
    toggle @disabled on submitButton until htmx:afterOnLoad
    end
end

behavior CopyToClipboard(text)
    on click call navigator.clipboard.writeText(text)
    then add @disabled to me
    then toggle .hidden on <div /> in me
    then wait 5s
    then toggle .hidden on <div /> in me
    then remove @disabled from me
end
"""

# Hyperscript for the global HTMX activity spinner.
_SPINNER_HYPERSCRIPT = """
on htmx:beforeSend from document
  remove .hidden
end
on htmx:historyRestore from document
  add .hidden
end
on htmx:afterOnLoad from document
  add .hidden
end
"""


@contextlib.contextmanager
def title(title_parts: Sequence[str]) -> Generator[None]:
    """Render an OOB-swappable ``<title>`` element.

    When the page is updated via HTMX boost the browser tab title is
    kept in sync thanks to ``hx-swap-oob``.
    """
    with tag.title(id="page_title", hx_swap_oob="true"):
        text(" \u00b7 ".join((*title_parts, _TITLE_SUFFIX)))
    yield


@contextlib.contextmanager
def base(request: Request, title_parts: Sequence[str]) -> Generator[None]:
    """Emit the full ``<html>`` document wrapper.

    Includes viewport meta, stylesheet, script bundle, Hyperscript
    behaviours, a modal root, and a global loading spinner.
    """
    with tag.html(lang="en"):
        with tag.head():
            with tag.meta(charset="utf-8"):
                pass
            with tag.meta(
                name="viewport", content="width=device-width, initial-scale=1.0"
            ):
                pass
            with tag.link(
                href=static_url(request, "styles.css"),
                rel="stylesheet",
                type="text/css",
            ):
                pass
            with tag.script(src=static_url(request, "scripts.js")):
                pass
            with title(title_parts):
                pass
            with tag.script(type="text/hyperscript"):
                text(_GLOBAL_HYPERSCRIPT)

        with tag.body():
            yield

            # Target element for HTMX-loaded modals.
            with tag.div(id="modal"):
                pass

            # Tiny spinner shown while any HTMX request is in flight.
            with tag.div(
                classes="absolute z-40 bottom-1 right-1 hidden",
                _=_SPINNER_HYPERSCRIPT,
            ):
                with tag.span(classes="loading loading-spinner loading-sm"):
                    pass


__all__ = ["base", "title"]
