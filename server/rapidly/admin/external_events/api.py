"""Admin panel external-event browser routes (HTMX).

Provides server-rendered views for inspecting raw external events
(Stripe webhooks, GitHub callbacks) with payload detail views and
a one-click resend action.
"""

import urllib.parse
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import UUID4, BeforeValidator
from tagflow import tag, text

from rapidly.analytics.external_event import actions as external_event_service
from rapidly.analytics.external_event import ordering
from rapidly.analytics.external_event.ordering import ExternalEventSortProperty
from rapidly.analytics.external_event.queries import ExternalEventRepository
from rapidly.core.pagination import PaginationParamsQuery
from rapidly.core.types import empty_str_to_none
from rapidly.models import ExternalEvent
from rapidly.models.external_event import ExternalEventSource
from rapidly.postgres import (
    AsyncReadSession,
    AsyncSession,
    get_db_read_session,
    get_db_session,
)

from ..components import button, datatable, input, modal
from ..layout import layout
from ..toast import add_toast
from .queries import AdminExternalEventRepository

router = APIRouter()

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_LOGFIRE_BASE = "https://logfire-us.pydantic.dev/rapidly/production-worker"


def _logfire_url(evt: ExternalEvent) -> str:
    """Build a deep-link into Logfire for the processing run of *evt*."""
    qs = urllib.parse.urlencode(
        {
            "q": (
                f"attributes->>'actor' = '{evt.task_name}' "
                f"AND attributes->'message'->'args'->>0 = '{evt.id}'"
            ),
            "since": evt.created_at.isoformat(),
        }
    )
    return f"{_LOGFIRE_BASE}?{qs}"


_HANDLED_CHOICES: list[tuple[str, str]] = [
    ("All Statuses", ""),
    ("Handled", "true"),
    ("Unhandled", "false"),
]


def _stripe_event_url(event_id: str) -> str:
    return f"https://dashboard.stripe.com/events/{event_id}"


# ---------------------------------------------------------------------------
# List view
# ---------------------------------------------------------------------------


@router.get("/", name="external_events:list")
async def list(
    request: Request,
    pagination: PaginationParamsQuery,
    sorting: ordering.ListSorting,
    query: str | None = Query(None),
    handled: Annotated[bool | None, BeforeValidator(empty_str_to_none), Query()] = None,
    session: AsyncReadSession = Depends(get_db_read_session),
) -> None:
    admin_repo = AdminExternalEventRepository.from_session(session)
    stmt = admin_repo.get_list_statement(query=query, handled=handled)

    domain_repo = ExternalEventRepository.from_session(session)
    stmt = domain_repo.apply_sorting(stmt, sorting)

    items, count = await admin_repo.paginate(
        stmt, limit=pagination.limit, page=pagination.page
    )

    with layout(
        request,
        [("External Events", str(request.url_for("external_events:list")))],
        "external_events:list",
    ):
        with tag.div(classes="flex flex-col gap-4"):
            with tag.h1(classes="text-4xl"):
                text("External Events")
            with tag.form(method="GET", classes="w-full flex flex-row gap-2"):
                with input.search("query", query):
                    pass
                with input.select(
                    _HANDLED_CHOICES,
                    "" if handled is None else str(handled).lower(),
                    name="handled",
                ):
                    pass
                with button(type="submit"):
                    text("Filter")

            with datatable.Datatable[ExternalEvent, ExternalEventSortProperty](
                datatable.DatatableActionsColumn(
                    "",
                    datatable.DatatableActionLink[ExternalEvent](
                        "View in Logfire",
                        lambda _, i: _logfire_url(i),
                        target="_blank",
                    ),
                    datatable.DatatableActionHTMX[ExternalEvent](
                        "Resend",
                        lambda r, i: str(r.url_for("external_events:resend", id=i.id)),
                        target="#modal",
                        hidden=lambda _, i: i.is_handled,
                    ),
                ),
                datatable.DatatableAttrColumn("id", "ID", clipboard=True),
                datatable.DatatableDateTimeColumn(
                    "created_at",
                    "Created At",
                    sorting=ExternalEventSortProperty.created_at,
                ),
                datatable.DatatableDateTimeColumn(
                    "handled_at",
                    "Handled At",
                    sorting=ExternalEventSortProperty.handled_at,
                ),
                datatable.DatatableAttrColumn("source", "Source"),
                datatable.DatatableAttrColumn(
                    "external_id",
                    "External ID",
                    external_href=lambda _, item: (
                        _stripe_event_url(item.external_id)
                        if item.source == ExternalEventSource.stripe
                        else None
                    ),
                ),
                datatable.DatatableAttrColumn("task_name", "Task Name", clipboard=True),
            ).render(request, items, sorting=sorting):
                pass
            with datatable.pagination(request, pagination, count):
                pass


# ---------------------------------------------------------------------------
# Resend action
# ---------------------------------------------------------------------------


@router.api_route(
    "/{id}/resend", name="external_events:resend", methods=["GET", "POST"]
)
async def resend(
    request: Request,
    id: UUID4,
    session: AsyncSession = Depends(get_db_session),
) -> Any:
    repo = ExternalEventRepository.from_session(session)
    evt = await repo.get_by_id(id)

    if evt is None:
        raise HTTPException(status_code=404)

    if request.method == "POST":
        await external_event_service.resend(evt)
        await add_toast(request, "Event has been enqueued for processing.", "success")
        return

    with modal(f"Resend Event {evt.id}", open=True):
        with tag.div(classes="flex flex-col gap-4"):
            with tag.p():
                text("Are you sure you want to resend this event? ")
                text("It'll be enqueued for processing again using the task ")
                with tag.code():
                    text(evt.task_name)
                text(".")
            with tag.div(classes="modal-action"):
                with tag.form(method="dialog"):
                    with button(ghost=True):
                        text("Cancel")
                with button(
                    type="button",
                    variant="primary",
                    hx_post=str(request.url),
                    hx_target="#modal",
                ):
                    text("Resend")
