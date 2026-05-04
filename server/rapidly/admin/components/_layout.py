"""Page layout skeleton: sidebar drawer, breadcrumbs, and HTMX boost.

For HTMX-boosted navigations (``HX-Boosted`` header targeting
``#content``), only the breadcrumb area, page title, and sidebar menu
are re-rendered so the browser can swap them in-place.  Full-page
loads get the complete HTML document.
"""

import contextlib
from collections.abc import Generator, Sequence

from fastapi import Request
from tagflow import tag, text

from ._base import base, title
from ._navigation import NavigationItem

# ---------------------------------------------------------------------------
# Partial fragments
# ---------------------------------------------------------------------------


@contextlib.contextmanager
def content(
    request: Request,
    breadcrumbs: Sequence[tuple[str, str]],
) -> Generator[None]:
    """Breadcrumb trail and main content wrapper."""
    with tag.div(classes="breadcrumbs text-sm"):
        with tag.ul():
            # Breadcrumbs arrive most-specific-first; we display
            # them root-first, so reverse and prepend the home link.
            all_crumbs = [
                *breadcrumbs,
                ("Rapidly Admin panel", str(request.url_for("index"))),
            ]
            for crumb_label, crumb_href in reversed(all_crumbs):
                with tag.li():
                    with tag.a(href=crumb_href):
                        text(crumb_label)
        yield


@contextlib.contextmanager
def menu(
    request: Request,
    navigation: list[NavigationItem],
    active_route_name: str,
) -> Generator[None]:
    """OOB-swappable sidebar menu list."""
    with tag.ul(classes="menu w-full", id="menu", hx_swap_oob="true"):
        for nav_item in navigation:
            with nav_item.render(request, active_route_name):
                pass
    yield


# ---------------------------------------------------------------------------
# Full page vs. HTMX partial dispatch
# ---------------------------------------------------------------------------


@contextlib.contextmanager
def layout(
    request: Request,
    breadcrumbs: Sequence[tuple[str, str]],
    navigation: list[NavigationItem],
    active_route_name: str,
) -> Generator[None]:
    """Top-level entry point for rendering an admin page.

    Detects HTMX boosted requests and skips the outer document shell
    when only the content pane needs updating.
    """
    title_parts = [label for label, _href in breadcrumbs]

    # Fast path: HTMX partial swap of the content area only.
    if (
        request.headers.get("HX-Boosted")
        and request.headers.get("HX-Target") == "content"
    ):
        with content(request, breadcrumbs):
            yield
        with title(title_parts):
            pass
        with menu(request, navigation, active_route_name):
            pass
        return

    # Full document render with sidebar drawer.
    with base(request, title_parts):
        with tag.div(classes="drawer lg:drawer-open"):
            with tag.input(id="menu-toggle", type="checkbox", classes="drawer-toggle"):
                pass

            with tag.main(classes="drawer-content"):
                # Mobile hamburger
                with tag.div(classes="flex flex-row items-center"):
                    with tag.label(
                        classes="btn btn-ghost drawer-button lg:hidden",
                        **{"for": "menu-toggle"},
                    ):
                        with tag.div(classes="icon-menu"):
                            pass

                with tag.div(classes="flex flex-col gap-4 p-4"):
                    with tag.div(
                        id="content",
                        classes="h-full w-full",
                        hx_boost="true",
                        hx_target="#content",
                    ):
                        with content(request, breadcrumbs):
                            yield

            # Sidebar
            with tag.aside(classes="drawer-side"):
                with tag.label(
                    classes="drawer-overlay",
                    **{"for": "menu-toggle"},
                ):
                    pass

                with tag.div(
                    classes=(
                        "bg-base-200 text-base-content min-h-full "
                        "w-60 p-4 flex flex-col gap-4"
                    )
                ):
                    with tag.a(
                        href=str(request.url_for("index")),
                        classes="flex justify-center",
                    ):
                        with tag.img(
                            src=str(request.url_for("static", path="logo.light.svg")),
                            classes="h-8 dark:hidden",
                        ):
                            pass
                        with tag.img(
                            src=str(request.url_for("static", path="logo.dark.svg")),
                            classes="h-8 dark:block hidden",
                        ):
                            pass

                    with menu(request, navigation, active_route_name):
                        pass


__all__ = ["layout"]
