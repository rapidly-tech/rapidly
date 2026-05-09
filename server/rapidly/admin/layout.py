"""Top-level page shell for the Rapidly admin panel.

Wraps every admin page in the shared sidebar + breadcrumb chrome by
delegating to the layout component and the navigation definition.
"""

import contextlib
from collections.abc import Generator, Sequence

from fastapi import Request

from .components import layout as layout_component
from .navigation import NAVIGATION


@contextlib.contextmanager
def layout(
    request: Request, breadcrumbs: Sequence[tuple[str, str]], active_route_name: str
) -> Generator[None]:
    """Render the full admin shell around the caller's content block.

    Handles two rendering paths transparently:

    * **HTMX boosted** -- only the content pane, page title, and sidebar
      menu are emitted so the browser can swap them in-place.
    * **Full page** -- the complete HTML document including the sidebar
      drawer, responsive hamburger toggle, and logo is rendered.

    Args:
        request: Current request; used to generate URLs and detect
            whether the request is an HTMX partial.
        breadcrumbs: ``(label, href)`` pairs representing the path to
            the current page, ordered from most-specific to least.
        active_route_name: FastAPI route name that should be highlighted
            in the sidebar menu.
    """
    with layout_component(
        request,
        breadcrumbs=breadcrumbs,
        navigation=NAVIGATION,
        active_route_name=active_route_name,
    ):
        yield
