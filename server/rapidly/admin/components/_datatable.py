"""Sortable, paginated data-table for admin panel list views.

The module exposes column types (text, datetime, currency, boolean,
actions), a ``Datatable`` container that wires them together, and a
standalone ``pagination`` helper for prev/next navigation.
"""

import contextlib
import secrets
import typing
from collections.abc import Callable, Generator, Sequence
from datetime import datetime
from enum import Enum, StrEnum, auto
from inspect import isgenerator
from operator import attrgetter
from typing import Any, Protocol

from fastapi import Request
from fastapi.datastructures import URL
from tagflow import attr, classes, tag, text

from rapidly.core.ordering import Sorting
from rapidly.core.pagination import PaginationParams

from .. import formatters
from ._clipboard_button import clipboard_button

# ---------------------------------------------------------------------------
# Column hierarchy
# ---------------------------------------------------------------------------


class DatatableColumn[M]:
    """Base column -- subclasses implement :meth:`render`."""

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


class DatatableSortingColumn[M, PE: StrEnum](DatatableColumn[M]):
    """Column that declares a sortable field identifier."""

    sorting: PE | None

    def __init__(self, label: str, sorting: PE | None = None) -> None:
        self.sorting = sorting
        super().__init__(label)


class DatatableAttrColumn[M, PE: StrEnum](DatatableSortingColumn[M, PE]):
    """Column that reads an object attribute and renders it as text.

    Optionally wraps the value in a link and/or adds a clipboard button.
    """

    attr: str
    clipboard: bool
    href_getter: Callable[[Request, M], str | None] | None
    external_href: bool

    @typing.overload
    def __init__(
        self,
        attr: str,
        label: str | None = None,
        *,
        clipboard: bool = False,
        href_route_name: str,
        sorting: PE | None = None,
    ) -> None: ...

    @typing.overload
    def __init__(
        self,
        attr: str,
        label: str | None = None,
        *,
        clipboard: bool = False,
        external_href: Callable[[Request, M], str | None],
        sorting: PE | None = None,
    ) -> None: ...

    @typing.overload
    def __init__(
        self,
        attr: str,
        label: str | None = None,
        *,
        sorting: PE | None = None,
        clipboard: bool = False,
    ) -> None: ...

    def __init__(
        self,
        attr: str,
        label: str | None = None,
        *,
        sorting: PE | None = None,
        clipboard: bool = False,
        href_route_name: str | None = None,
        external_href: Callable[[Request, M], str | None] | None = None,
    ) -> None:
        self.attr = attr
        self.clipboard = clipboard
        self.href_getter = None
        self.external_href = False

        if external_href is not None:
            self.href_getter = external_href
            self.external_href = True
        elif href_route_name is not None:
            self.href_getter = lambda r, i: str(
                r.url_for(href_route_name, id=getattr(i, "id"))
            )

        super().__init__(label or attr, sorting)

    # -- value access --

    def get_raw_value(self, item: M) -> Any:
        return attrgetter(self.attr)(item)

    def get_value(self, item: M) -> str | None:
        raw = self.get_raw_value(item)
        return None if raw is None else str(raw)

    # -- rendering --

    def render(self, request: Request, item: M) -> Generator[None] | None:
        display = self.get_value(item)
        link = self.href_getter(request, item) if self.href_getter else None

        with tag.div(classes="flex items-center gap-1"):
            wrapper = tag.a if link else tag.div
            with wrapper():
                if link:
                    classes("link")
                    attr("href", str(link))
                    if self.external_href:
                        attr("target", "_blank")
                        attr("rel", "noopener noreferrer")
                text(display if display is not None else "\u2014")
            if display is not None and self.clipboard:
                with clipboard_button(display):
                    pass
        return None

    def __repr__(self) -> str:
        return f"{type(self).__name__}(attr={self.attr!r}, label={self.label!r})"


class DatatableDateTimeColumn[M, PE: StrEnum](DatatableAttrColumn[M, PE]):
    """Formats a ``datetime`` attribute through the admin date formatter."""

    def get_value(self, item: M) -> str | None:
        raw: datetime | None = self.get_raw_value(item)
        return None if raw is None else formatters.datetime(raw)


class DatatableBooleanColumn[M, PE: StrEnum](DatatableAttrColumn[M, PE]):
    """Renders boolean values as check / cross icons."""

    def render(self, request: Request, item: M) -> Generator[None] | None:
        raw = self.get_raw_value(item)
        with tag.div():
            if raw is None:
                text("\u2014")
            elif raw:
                with tag.div(classes="icon-check"):
                    pass
            else:
                with tag.div(classes="icon-close"):
                    pass
        return None


# ---------------------------------------------------------------------------
# Row actions
# ---------------------------------------------------------------------------


class DatatableAction[M](Protocol):
    """Protocol for items inside an actions-column dropdown."""

    @contextlib.contextmanager
    def render(self, request: Request, item: M) -> Generator[None]: ...

    def is_hidden(self, request: Request, item: M) -> bool: ...


class DatatableActionLink[M](DatatableAction[M]):
    """Plain ``<a>`` navigation link."""

    def __init__(
        self,
        label: str,
        href: str | URL | Callable[[Request, M], str],
        target: str | None = None,
    ) -> None:
        self.label = label
        self.href = href
        self.target = target

    @contextlib.contextmanager
    def render(self, request: Request, item: M) -> Generator[None]:
        resolved = self.href(request, item) if callable(self.href) else str(self.href)
        with tag.a(href=resolved, target=self.target if self.target else None):
            text(self.label)
        yield

    def is_hidden(self, request: Request, item: M) -> bool:
        return False


class DatatableActionHTMX[M](DatatableAction[M]):
    """Button that fires an HTMX GET and swaps into *target*."""

    def __init__(
        self,
        label: str,
        href: str | URL | Callable[[Request, M], str],
        target: str,
        hidden: Callable[[Request, M], bool] | None = None,
    ) -> None:
        self.label = label
        self.href = href
        self.target = target
        self.hidden = hidden

    @contextlib.contextmanager
    def render(self, request: Request, item: M) -> Generator[None]:
        resolved = self.href(request, item) if callable(self.href) else str(self.href)
        with tag.button(type="button", hx_get=str(resolved), hx_target=self.target):
            text(self.label)
        yield

    def is_hidden(self, request: Request, item: M) -> bool:
        return self.hidden(request, item) if self.hidden else False


class DatatableActionsColumn[M](DatatableColumn[M]):
    """Column that shows an ellipsis menu with a popover of actions."""

    def __init__(self, label: str, *actions: DatatableAction[M]) -> None:
        self.actions = actions
        super().__init__(label)

    def render(self, request: Request, item: M) -> Generator[None] | None:
        visible = [a for a in self.actions if not a.is_hidden(request, item)]
        if not visible:
            return None

        uid = secrets.token_urlsafe(6)
        with tag.button(
            type="button",
            classes="btn btn-ghost m-1",
            popovertarget=f"popover-{uid}",
            style=f"anchor-name:--anchor-{uid}",
        ):
            with tag.div(classes="font-normal icon-ellipsis-vertical"):
                pass

        with tag.ul(
            classes="dropdown menu bg-base-100 rounded-box z-1 w-52 p-2 shadow-sm",
            popover=True,
            id=f"popover-{uid}",
            style=f"position-anchor:--anchor-{uid}",
        ):
            for action in visible:
                with tag.li():
                    with action.render(request, item):
                        pass
        return None


# ---------------------------------------------------------------------------
# Sort direction enum
# ---------------------------------------------------------------------------


class SortWay(Enum):
    ASC = auto()
    DESC = auto()


# ---------------------------------------------------------------------------
# Datatable container
# ---------------------------------------------------------------------------


class Datatable[M, PE: StrEnum]:
    """Full table with headers, sortable column links, and empty-state."""

    def __init__(
        self, *columns: DatatableColumn[M], empty_message: str | None = None
    ) -> None:
        self.columns = columns
        self.empty_message = empty_message or "No items found"

    @contextlib.contextmanager
    def render(
        self,
        request: Request,
        items: Sequence[M],
        *,
        sorting: list[Sorting[PE]] | None = None,
    ) -> Generator[None]:
        with tag.div(
            classes="overflow-x-auto rounded-box bg-base-100 border-1 border-base-200"
        ):
            with tag.table(classes="table table-auto"):
                self._render_head(request, sorting)
                self._render_body(request, items)
        yield

    # -- private helpers --

    def _render_head(self, request: Request, sorting: list[Sorting[PE]] | None) -> None:
        with tag.thead():
            with tag.tr():
                for col in self.columns:
                    with tag.th():
                        if (
                            sorting is None
                            or not isinstance(col, DatatableSortingColumn)
                            or col.sorting is None
                        ):
                            text(col.label)
                            continue

                        sort_url = self._build_sort_url(request, sorting, col)
                        with tag.a(href=str(sort_url), classes="flex gap-1"):
                            text(col.label)
                            direction = self._current_sort_direction(sorting, col)
                            with tag.div("font-normal"):
                                if direction == SortWay.ASC:
                                    classes("icon-sort-desc")
                                elif direction == SortWay.DESC:
                                    classes("icon-sort-asc")

    def _render_body(self, request: Request, items: Sequence[M]) -> None:
        with tag.tbody():
            if not items:
                with tag.tr():
                    with tag.td(
                        classes="text-2xl h-96 text-gray-500 text-center my-10",
                        colspan=len(self.columns),
                    ):
                        text(self.empty_message)
            else:
                for item in items:
                    with tag.tr():
                        for col in self.columns:
                            with tag.td():
                                with col._do_render(request, item):
                                    pass

    def _current_sort_direction(
        self, sorting: list[Sorting[PE]] | None, col: DatatableSortingColumn[M, PE]
    ) -> SortWay | None:
        if sorting is None or col.sorting is None:
            return None
        for field, descending in sorting:
            if field == col.sorting:
                return SortWay.DESC if descending else SortWay.ASC
        return None

    def _build_sort_url(
        self,
        request: Request,
        sorting: list[Sorting[PE]] | None,
        col: DatatableSortingColumn[M, PE],
    ) -> URL:
        base = request.url.remove_query_params("sorting")
        for field, descending in sorting or []:
            if field == col.sorting:
                if not descending:
                    return base.include_query_params(sorting=f"-{field.value}")
                # Already descending -- clicking again removes the sort.
                return base
        if col.sorting is not None:
            return base.include_query_params(sorting=col.sorting.value)
        return base

    def __repr__(self) -> str:
        return (
            f"{type(self).__name__}(columns={self.columns!r}, "
            f"empty_message={self.empty_message!r})"
        )


# ---------------------------------------------------------------------------
# Standalone pagination controls
# ---------------------------------------------------------------------------


@contextlib.contextmanager
def pagination(
    request: Request, pagination: PaginationParams, count: int
) -> Generator[None]:
    """Render prev/next pagination with an item-range summary.

    Args:
        request: Current request -- query params are preserved.
        pagination: Page number and page size.
        count: Total item count across all pages.
    """
    first_item = (pagination.page - 1) * pagination.limit + 1
    last_item = min(pagination.page * pagination.limit, count)

    has_next = last_item < count
    has_prev = first_item > 1

    next_url = (
        request.url.replace_query_params(
            **{**request.query_params, "page": pagination.page + 1}
        )
        if has_next
        else None
    )
    prev_url = (
        request.url.replace_query_params(
            **{**request.query_params, "page": pagination.page - 1}
        )
        if has_prev
        else None
    )

    with tag.div(classes="flex justify-between"):
        with tag.div(classes="text-sm"):
            text("Showing ")
            with tag.span(classes="font-bold"):
                text(str(first_item))
            text(" to ")
            with tag.span(classes="font-bold"):
                text(str(last_item))
            text(" of ")
            with tag.span(classes="font-bold"):
                text(str(count))
            text(" entries")

        with tag.div(classes="join grid grid-cols-2"):
            with tag.a(
                classes="join-item btn",
                href=str(prev_url) if prev_url else "",
            ):
                if prev_url is None:
                    attr("disabled", True)
                text("Previous")
            with tag.a(
                classes="join-item btn",
                href=str(next_url) if next_url else "",
            ):
                if next_url is None:
                    attr("disabled", True)
                text("Next")
    yield


__all__ = [
    "Datatable",
    "DatatableActionsColumn",
    "DatatableAttrColumn",
    "DatatableColumn",
    "DatatableDateTimeColumn",
    "pagination",
]
