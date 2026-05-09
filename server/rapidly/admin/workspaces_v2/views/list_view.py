"""Enhanced workspace list view with tabs, smart grouping, and quick actions.

Renders a paginated, sortable, filterable list of workspaces in the
admin panel with attention-priority grouping and advanced filters.
"""

import contextlib
import json
from collections.abc import Generator
from datetime import UTC, datetime

import pycountry
from fastapi import Request
from sqlalchemy import func, select
from tagflow import tag, text

from rapidly.models import Account, Workspace
from rapidly.models.workspace import WorkspaceStatus
from rapidly.postgres import AsyncReadSession, AsyncSession

from ...components import (
    Tab,
    action_bar,
    button,
    empty_state,
    status_badge,
    tab_nav,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Days threshold before a workspace is flagged as needing attention.
_REVIEW_ATTENTION_DAYS = 3

# Risk score threshold for "needs attention".
_RISK_ATTENTION_THRESHOLD = 80

# Column definitions for the workspace table.
_SORTABLE_COLUMNS: list[tuple[str, str, str]] = [
    # (label, sort_key, alignment)
    ("Workspace", "name", "left"),
    ("Country", "country", "left"),
    ("Created", "created", "left"),
    ("In Status", "status_duration", "center"),
    ("Risk", "risk", "center"),
    ("Next Review", "next_review", "right"),
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _days_since(dt: datetime) -> int:
    return (datetime.now(UTC) - dt).days


def _country_display(code: str) -> str:
    """Return 'XX - CountryName' or just the raw code."""
    country = pycountry.countries.get(alpha_2=code)
    name = country.name if country else code
    return f"{code} - {name}"


# ---------------------------------------------------------------------------
# View
# ---------------------------------------------------------------------------


class WorkspaceListView:
    """Render the enhanced workspace list view."""

    def __init__(self, session: AsyncSession | AsyncReadSession):
        self.session = session

    # -- data queries --

    async def get_status_counts(self) -> dict[WorkspaceStatus, int]:
        stmt = select(Workspace.status, func.count(Workspace.id).label("cnt")).group_by(
            Workspace.status
        )
        result = await self.session.execute(stmt)
        return {row.status: row.cnt for row in result}

    async def get_distinct_countries(self) -> list[str]:
        stmt = (
            select(Account.country)
            .join(Workspace, Workspace.account_id == Account.id)
            .where(Account.country.is_not(None))
            .distinct()
            .order_by(Account.country)
        )
        result = await self.session.execute(stmt)
        return [row[0] for row in result.all()]

    # -- classification --

    def calculate_days_in_status(self, ws: Workspace) -> int:
        ref = ws.status_updated_at or ws.created_at
        return _days_since(ref)

    def is_needs_attention(self, ws: Workspace) -> bool:
        if (
            ws.is_under_review
            and self.calculate_days_in_status(ws) > _REVIEW_ATTENTION_DAYS
        ):
            return True
        if (
            ws.review
            and ws.review.appeal_submitted_at
            and not ws.review.appeal_reviewed_at
        ):
            return True
        if (
            ws.review
            and ws.review.risk_score
            and ws.review.risk_score >= _RISK_ATTENTION_THRESHOLD
        ):
            return True
        return False

    # -- table header rendering --

    @contextlib.contextmanager
    def sortable_header(
        self,
        request: Request,
        label: str,
        sort_key: str,
        current_sort: str,
        current_direction: str,
        align: str = "left",
        status_filter: WorkspaceStatus | None = None,
    ) -> Generator[None]:
        is_active = current_sort == sort_key
        next_dir = "desc" if (is_active and current_direction == "asc") else "asc"
        indicator = ("↑" if current_direction == "asc" else "↓") if is_active else "↕"

        align_cls = {"center": "text-center", "right": "text-right"}.get(align, "")
        justify_cls = {"center": "justify-center", "right": "justify-end"}.get(
            align, "justify-start"
        )

        hx_params: dict[str, str] = {"sort": sort_key, "direction": next_dir}
        if status_filter is not None:
            hx_params["status"] = status_filter.value

        with tag.th(
            classes=f"cursor-pointer hover:bg-base-300 {align_cls}",
            **{
                "hx-get": str(request.url_for("workspaces-v2:list")),
                "hx-vals": json.dumps(hx_params),
                "hx-target": "#org-list",
                "hx-include": "#filter-form",
            },
        ):
            with tag.div(classes=f"flex items-center gap-1 {justify_cls}"):
                text(label)
                opacity = "opacity-100" if is_active else "opacity-50"
                with tag.span(classes=f"text-xs {opacity}"):
                    text(indicator)

        yield

    def _render_table_headers(
        self,
        request: Request,
        current_sort: str,
        current_direction: str,
        status_filter: WorkspaceStatus | None,
    ) -> None:
        """Emit the full thead row (sortable columns + Email + Actions)."""
        with tag.thead():
            with tag.tr():
                # First sortable column
                with self.sortable_header(
                    request,
                    "Workspace",
                    "name",
                    current_sort,
                    current_direction,
                    status_filter=status_filter,
                ):
                    pass

                with tag.th():
                    text("Email")

                # Remaining sortable columns
                for col_label, col_key, col_align in _SORTABLE_COLUMNS[1:]:
                    with self.sortable_header(
                        request,
                        col_label,
                        col_key,
                        current_sort,
                        current_direction,
                        col_align,
                        status_filter=status_filter,
                    ):
                        pass

                with tag.th(classes="text-right"):
                    text("Actions")

    # -- row rendering --

    @contextlib.contextmanager
    def workspace_row(
        self, request: Request, ws: Workspace, show_quick_actions: bool = False
    ) -> Generator[None]:
        days_in_status = self.calculate_days_in_status(ws)
        row_cls = "hover:bg-base-100"
        if self.is_needs_attention(ws):
            row_cls += " bg-error/5"

        with tag.tr(classes=row_cls):
            # Name + status badge
            with tag.td(classes="py-4"):
                with tag.div(classes="flex flex-col gap-1"):
                    with tag.a(
                        href=str(
                            request.url_for("workspaces-v2:detail", workspace_id=ws.id)
                        ),
                        classes="font-semibold hover:underline flex items-center gap-2",
                    ):
                        text(ws.name)
                        with status_badge(ws.status):
                            pass
                    with tag.div(classes="text-xs text-base-content/60 font-mono"):
                        text(ws.slug)
                    if (
                        ws.review
                        and ws.review.appeal_submitted_at
                        and not ws.review.appeal_reviewed_at
                    ):
                        with tag.span(classes="badge badge-info badge-xs mt-1"):
                            text("Appeal Pending")

            # Email
            with tag.td(classes="text-sm"):
                if ws.email:
                    with tag.span(classes="font-mono text-xs"):
                        text(ws.email)
                else:
                    with tag.span(classes="text-base-content/40"):
                        text("\u2014")

            # Country
            with tag.td(classes="text-sm"):
                if ws.account and ws.account.country:
                    text(ws.account.country)
                else:
                    with tag.span(classes="text-base-content/40"):
                        text("\u2014")

            # Created
            with tag.td(classes="text-sm"):
                text(f"{_days_since(ws.created_at)}d ago")

            # Days in status
            with tag.td(classes="text-sm font-semibold text-center"):
                text(f"{days_in_status}d")

            # Risk
            with tag.td(classes="text-sm text-center"):
                self._render_risk_cell(ws)

            # Next review
            with tag.td(classes="text-sm text-right"):
                if ws.next_review_threshold:
                    text(f"${ws.next_review_threshold / 100:,.0f}")
                else:
                    with tag.span(classes="text-base-content/40"):
                        text("\u2014")

            # Actions
            with tag.td(classes="text-right"):
                if show_quick_actions:
                    self._render_quick_actions(request, ws)
                else:
                    with tag.a(
                        href=str(
                            request.url_for("workspaces-v2:detail", workspace_id=ws.id)
                        ),
                        classes="btn btn-ghost btn-sm",
                    ):
                        text("View \u2192")

        yield

    @staticmethod
    def _render_risk_cell(ws: Workspace) -> None:
        if ws.review and ws.review.risk_score is not None:
            score = ws.review.risk_score
            color = (
                "text-error"
                if score >= 75
                else ("text-warning" if score >= 50 else "text-success")
            )
            with tag.span(classes=f"font-bold {color}"):
                text(str(score))
        else:
            with tag.span(classes="text-base-content/40"):
                text("\u2014")

    @staticmethod
    def _render_quick_actions(request: Request, ws: Workspace) -> None:
        with tag.div(classes="flex gap-2 justify-end"):
            with button(
                variant="secondary",
                size="sm",
                outline=True,
                hx_post=str(
                    request.url_for("workspaces-v2:approve", workspace_id=ws.id)
                )
                + "?threshold=25000",
                hx_confirm="Approve with $250 threshold?",
            ):
                text("Approve")
            with button(
                variant="secondary",
                size="sm",
                outline=True,
                hx_get=str(
                    request.url_for("workspaces-v2:deny_dialog", workspace_id=ws.id)
                ),
                hx_target="#modal",
            ):
                text("Deny")

    # -- table body (shared between render + render_table_only) --

    def _render_workspace_table(
        self,
        request: Request,
        workspaces: list[Workspace],
        status_filter: WorkspaceStatus | None,
        current_sort: str,
        current_direction: str,
        page: int,
        has_more: bool,
    ) -> None:
        if not workspaces:
            with empty_state(
                "No Workspaces Found", "No workspaces match your current filters."
            ):
                pass
            return

        flagged = [w for w in workspaces if self.is_needs_attention(w)]
        regular = [w for w in workspaces if not self.is_needs_attention(w)]

        # Attention section
        if flagged and status_filter is None:
            with tag.div(classes="mb-8"):
                with tag.h2(classes="text-xl font-bold mb-4 flex items-center gap-3"):
                    text("Needs Attention")
                    with tag.span(classes="badge badge-error badge-lg"):
                        text(str(len(flagged)))

                with tag.table(classes="table table-zebra w-full"):
                    self._render_table_headers(
                        request, current_sort, current_direction, status_filter
                    )
                    with tag.tbody():
                        for w in flagged:
                            with self.workspace_row(
                                request, w, show_quick_actions=True
                            ):
                                pass

            with tag.div(classes="divider my-8"):
                text("All Workspaces")

        # Main table
        visible = regular if status_filter is None else workspaces
        if visible or status_filter is not None:
            with tag.table(classes="table table-zebra w-full"):
                self._render_table_headers(
                    request, current_sort, current_direction, status_filter
                )
                with tag.tbody():
                    for w in visible:
                        with self.workspace_row(request, w):
                            pass

        # Pagination
        if has_more:
            with tag.div(classes="flex justify-center mt-6"):
                with button(
                    variant="secondary",
                    hx_get=str(request.url_for("workspaces-v2:list"))
                    + f"?page={page + 1}",
                    hx_target="#org-list",
                    hx_swap="beforeend",
                ):
                    text("Load More")

    # -- filters --

    def _render_filters(
        self,
        request: Request,
        status_filter: WorkspaceStatus | None,
        status_counts: dict[WorkspaceStatus, int],
        countries: list[str] | None,
        selected_country: str | None,
    ) -> None:
        # Tabs
        all_count = sum(status_counts.values())
        tabs = [
            Tab(
                label="All",
                url=str(request.url_for("workspaces-v2:list")),
                active=status_filter is None,
                count=all_count,
            ),
            Tab(
                label="Initial Review",
                url=str(request.url_for("workspaces-v2:list"))
                + "?status=initial_review",
                active=status_filter == WorkspaceStatus.INITIAL_REVIEW,
                count=status_counts.get(WorkspaceStatus.INITIAL_REVIEW, 0),
                badge_variant="warning",
            ),
            Tab(
                label="Ongoing Review",
                url=str(request.url_for("workspaces-v2:list"))
                + "?status=ongoing_review",
                active=status_filter == WorkspaceStatus.ONGOING_REVIEW,
                count=status_counts.get(WorkspaceStatus.ONGOING_REVIEW, 0),
                badge_variant="warning",
            ),
            Tab(
                label="Active",
                url=str(request.url_for("workspaces-v2:list")) + "?status=active",
                active=status_filter == WorkspaceStatus.ACTIVE,
                count=status_counts.get(WorkspaceStatus.ACTIVE, 0),
                badge_variant="success",
            ),
            Tab(
                label="Denied",
                url=str(request.url_for("workspaces-v2:list")) + "?status=denied",
                active=status_filter == WorkspaceStatus.DENIED,
                count=status_counts.get(WorkspaceStatus.DENIED, 0),
                badge_variant="error",
            ),
        ]
        with tab_nav(tabs):
            pass

        # Search + advanced filter form
        with tag.div(classes="my-6"):
            with tag.form(
                id="filter-form",
                classes="space-y-4",
                hx_get=str(request.url_for("workspaces-v2:list")),
                hx_trigger="submit, change from:.filter-select",
                hx_target="#org-list",
            ):
                self._render_search_row(request)
                self._render_advanced_filters(countries, selected_country)

    def _render_search_row(self, request: Request) -> None:
        with tag.div(classes="flex gap-3"):
            with tag.div(classes="flex-1"):
                with tag.input(
                    type="search",
                    placeholder="Search workspaces by name, slug, or email...",
                    classes="input input-bordered w-full",
                    name="q",
                    **{"hx-trigger": "keyup changed delay:300ms"},
                ):
                    pass

            with tag.button(
                type="button",
                id="filter-toggle-btn",
                classes="btn btn-outline gap-2",
                **{"_": "on click toggle .hidden on #advanced-filters"},
            ):
                with tag.svg(
                    xmlns="http://www.w3.org/2000/svg",
                    classes="h-5 w-5",
                    fill="none",
                    viewBox="0 0 24 24",
                    stroke="currentColor",
                ):
                    with tag.path(
                        **{
                            "stroke-linecap": "round",
                            "stroke-linejoin": "round",
                            "stroke-width": "2",
                            "d": "M3 4a1 1 0 011-1h16a1 1 0 011 1v2.586a1 1 0 01-.293.707l-6.414 6.414a1 1 0 00-.293.707V17l-4 4v-6.586a1 1 0 00-.293-.707L3.293 7.293A1 1 0 013 6.586V4z",
                        }
                    ):
                        pass
                text("Filters")

            with tag.button(
                type="button",
                id="clear-filters-btn",
                classes="btn btn-ghost",
                **{
                    "_": "on click set value of <input.filter-input/> to '' then set value of <select.filter-select/> to '' then trigger submit on #filter-form"
                },
            ):
                text("Clear")

    def _render_advanced_filters(
        self, countries: list[str] | None, selected_country: str | None
    ) -> None:
        with tag.div(
            id="advanced-filters", classes="hidden mt-4 p-4 bg-base-200 rounded-lg"
        ):
            with tag.div(classes="space-y-3"):
                with tag.div(classes="grid grid-cols-1 md:grid-cols-3 gap-3"):
                    self._render_country_filter(countries, selected_country)
                    self._render_risk_filter()
                    self._render_days_filter()

                with tag.div(classes="grid grid-cols-1 md:grid-cols-3 gap-3"):
                    self._render_appeal_filter()

    @staticmethod
    def _render_country_filter(
        countries: list[str] | None, selected: str | None
    ) -> None:
        with tag.div():
            with tag.label(classes="label"):
                with tag.span(classes="label-text text-xs font-semibold"):
                    text("Country")
            with tag.select(
                classes="select select-bordered select-sm w-full filter-select",
                name="country",
            ):
                with tag.option(value=""):
                    text("All Countries")
                if countries:
                    for code in countries:
                        attrs: dict[str, str] = {"value": code}
                        if selected == code:
                            attrs["selected"] = ""
                        with tag.option(**attrs):
                            text(_country_display(code))

    @staticmethod
    def _render_risk_filter() -> None:
        with tag.div():
            with tag.label(classes="label"):
                with tag.span(classes="label-text text-xs font-semibold"):
                    text("Risk Level")
            with tag.select(
                classes="select select-bordered select-sm w-full filter-select",
                name="risk_level",
            ):
                for val, label in [
                    ("", "All Risk Levels"),
                    ("high", "High (\u226575)"),
                    ("medium", "Medium (50-74)"),
                    ("low", "Low (<50)"),
                    ("unscored", "Unscored"),
                ]:
                    with tag.option(value=val):
                        text(label)

    @staticmethod
    def _render_days_filter() -> None:
        with tag.div():
            with tag.label(classes="label"):
                with tag.span(classes="label-text text-xs font-semibold"):
                    text("Days in Status")
            with tag.select(
                classes="select select-bordered select-sm w-full filter-select",
                name="days_in_status",
            ):
                for val, label in [
                    ("", "Any Duration"),
                    ("1", ">1 day"),
                    ("3", ">3 days"),
                    ("7", ">7 days"),
                    ("30", ">30 days"),
                ]:
                    with tag.option(value=val):
                        text(label)

    @staticmethod
    def _render_appeal_filter() -> None:
        with tag.div():
            with tag.label(classes="label"):
                with tag.span(classes="label-text text-xs font-semibold"):
                    text("Appeal Status")
            with tag.select(
                classes="select select-bordered select-sm w-full filter-select",
                name="has_appeal",
            ):
                for val, label in [
                    ("", "All"),
                    ("pending", "Pending Appeal"),
                    ("reviewed", "Reviewed"),
                    ("none", "No Appeal"),
                ]:
                    with tag.option(value=val):
                        text(label)

    # -- public entry points --

    @contextlib.contextmanager
    def render(
        self,
        request: Request,
        workspaces: list[Workspace],
        status_filter: WorkspaceStatus | None,
        status_counts: dict[WorkspaceStatus, int],
        page: int,
        has_more: bool,
        current_sort: str = "priority",
        current_direction: str = "asc",
        countries: list[str] | None = None,
        selected_country: str | None = None,
    ) -> Generator[None]:
        """Render the complete list view (header + tabs + filters + table)."""
        with tag.div(classes="flex items-center justify-between mb-8"):
            with tag.h1(classes="text-3xl font-bold"):
                text("Workspaces")
            with action_bar(position="right"):
                with button(
                    variant="primary",
                    hx_get=str(request.url_for("workspaces-v2:list")) + "/new",
                    hx_target="#modal",
                ):
                    text("+ Create Thread")

        self._render_filters(
            request, status_filter, status_counts, countries, selected_country
        )

        with tag.div(id="org-list", classes="overflow-x-auto"):
            self._render_workspace_table(
                request,
                workspaces,
                status_filter,
                current_sort,
                current_direction,
                page,
                has_more,
            )

        yield

    @contextlib.contextmanager
    def render_table_only(
        self,
        request: Request,
        workspaces: list[Workspace],
        status_filter: WorkspaceStatus | None,
        status_counts: dict[WorkspaceStatus, int],
        page: int,
        has_more: bool,
        current_sort: str = "priority",
        current_direction: str = "asc",
    ) -> Generator[None]:
        """Render only the workspace table (for HTMX partial updates)."""
        with tag.div(id="org-list", classes="overflow-x-auto"):
            self._render_workspace_table(
                request,
                workspaces,
                status_filter,
                current_sort,
                current_direction,
                page,
                has_more,
            )
        yield


__all__ = ["WorkspaceListView"]
