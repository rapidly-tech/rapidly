"""Sidebar navigation items with active-state detection.

A :class:`NavigationItem` is either a direct link (string route name)
or a collapsible group of child items (list of children).  The sidebar
renderer calls :meth:`render` on each top-level item, which recurses
into children as needed.
"""

import contextlib
from collections.abc import Generator
from typing import overload

from fastapi import Request
from tagflow import attr, classes, tag, text


class NavigationItem:
    """One entry in the sidebar -- link leaf or expandable group."""

    label: str
    route_name: str | None
    active_route_name_prefix: str | None
    children: list["NavigationItem"]

    @overload
    def __init__(
        self,
        label: str,
        route_name_or_children: str,
        *,
        active_route_name_prefix: str | None = None,
    ) -> None: ...

    @overload
    def __init__(
        self,
        label: str,
        route_name_or_children: list["NavigationItem"],
        *,
        active_route_name_prefix: str | None = None,
    ) -> None: ...

    def __init__(
        self,
        label: str,
        route_name_or_children: str | list["NavigationItem"],
        *,
        active_route_name_prefix: str | None = None,
    ) -> None:
        self.label = label
        self.active_route_name_prefix = active_route_name_prefix

        if isinstance(route_name_or_children, str):
            self.route_name = route_name_or_children
            self.children = []
        else:
            self.route_name = None
            self.children = route_name_or_children

    # -- active-state logic --

    def _is_active(self, current_route: str) -> bool:
        """Check whether *current_route* falls under this item's scope."""
        if self.active_route_name_prefix is not None:
            return current_route.startswith(self.active_route_name_prefix)
        if self.route_name is not None:
            return self.route_name == current_route
        return any(child._is_active(current_route) for child in self.children)

    # -- HTML output --

    @contextlib.contextmanager
    def render(self, request: Request, active_route_name: str) -> Generator[None]:
        """Emit the ``<li>`` for this navigation entry.

        Leaf items produce an ``<a>``; group items produce a
        ``<details>/<summary>`` with nested ``<ul>``.
        """
        active = self._is_active(active_route_name)

        with tag.li():
            if self.route_name is not None:
                with tag.a(href=str(request.url_for(self.route_name))):
                    if active:
                        classes("menu-active")
                    text(self.label)
            elif self.children:
                with tag.details():
                    if active:
                        attr("open", True)
                    with tag.summary():
                        text(self.label)
                    with tag.ul():
                        for child in self.children:
                            with child.render(request, active_route_name):
                                pass
        yield


__all__ = ["NavigationItem"]
