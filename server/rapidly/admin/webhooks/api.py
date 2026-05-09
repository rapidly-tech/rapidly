"""Admin panel webhook management (HTMX).

Server-rendered views for listing webhook endpoints, inspecting
details, and toggling enabled/disabled status.
"""

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import UUID4
from sqlalchemy.orm import joinedload
from tagflow import attr, tag, text

from rapidly.core.pagination import PaginationParamsQuery
from rapidly.messaging.webhook import actions as webhook_service
from rapidly.messaging.webhook.ordering import WebhookSortProperty
from rapidly.messaging.webhook.queries import WebhookEndpointRepository
from rapidly.messaging.webhook.types import WebhookEndpointUpdate
from rapidly.models import WebhookEndpoint
from rapidly.postgres import (
    AsyncReadSession,
    AsyncSession,
    get_db_read_session,
    get_db_session,
)

from ..components import button, confirmation_dialog, datatable, description_list, input
from ..layout import layout
from ..toast import add_toast
from .queries import AdminWebhookRepository

router = APIRouter()


# ---------------------------------------------------------------------------
# Detail view
# ---------------------------------------------------------------------------


@router.get("/{id}", name="webhooks:get")
async def get(
    request: Request,
    id: UUID4,
    session: AsyncReadSession = Depends(get_db_read_session),
) -> None:
    repo = WebhookEndpointRepository.from_session(session)
    wh = await repo.get_by_id(
        id,
        options=(joinedload(WebhookEndpoint.workspace),),
    )

    if wh is None:
        raise HTTPException(status_code=404)

    with layout(
        request,
        [
            (f"{wh.url}", str(request.url)),
            ("Webhooks", str(request.url_for("webhooks:list"))),
        ],
        "webhooks:get",
    ):
        with tag.div(classes="flex flex-col gap-4"):
            with tag.div(classes="flex justify-between items-center"):
                with tag.h1(classes="text-4xl"):
                    text(f"Webhook: {wh.url}")

            with tag.div(classes="grid grid-cols-1 lg:grid-cols-2 gap-4"):
                # Webhook details card
                with tag.div(classes="card card-border w-full shadow-sm"):
                    with tag.div(classes="card-body"):
                        with tag.h2(classes="card-title"):
                            text("Webhook Details")
                        with tag.div(id="webhook-details-list"):
                            with description_list.DescriptionList[WebhookEndpoint](
                                description_list.DescriptionListAttrItem(
                                    "id", "ID", clipboard=True
                                ),
                                description_list.DescriptionListAttrItem("url", "URL"),
                                description_list.DescriptionListAttrItem(
                                    "format", "Format"
                                ),
                                description_list.DescriptionListAttrItem(
                                    "enabled", "Enabled"
                                ),
                                description_list.DescriptionListDateTimeItem(
                                    "created_at", "Created At"
                                ),
                                description_list.DescriptionListDateTimeItem(
                                    "modified_at", "Modified At"
                                ),
                            ).render(request, wh):
                                pass

                        with tag.div(classes="divider"):
                            pass

                        with tag.div(
                            id="webhook-enabled-status",
                            classes="flex items-center justify-between",
                        ):
                            with tag.span(classes="label-text font-medium"):
                                text("Enabled")
                            with button(
                                variant="success" if wh.enabled else "neutral",
                                size="sm",
                                hx_get=str(
                                    request.url_for(
                                        "webhooks:confirm_toggle_enabled", id=wh.id
                                    )
                                ),
                                hx_target="#modal",
                            ):
                                text("Enabled" if wh.enabled else "Disabled")

                # Workspace card
                with tag.div(classes="card card-border w-full shadow-sm"):
                    with tag.div(classes="card-body"):
                        with tag.h2(classes="card-title"):
                            text("Workspace")
                        with description_list.DescriptionList[WebhookEndpoint](
                            description_list.DescriptionListLinkItem[WebhookEndpoint](
                                "workspace.name",
                                "Name",
                                href_getter=lambda r, i: str(
                                    r.url_for("workspaces:get", id=i.workspace_id)
                                ),
                            ),
                            description_list.DescriptionListAttrItem(
                                "workspace.slug", "Slug"
                            ),
                            description_list.DescriptionListAttrItem(
                                "workspace_id", "ID", clipboard=True
                            ),
                        ).render(request, wh):
                            pass

            # Event subscriptions
            with tag.div(classes="flex flex-col gap-4 pt-8"):
                with tag.h2(classes="text-2xl"):
                    text("Subscribed Events")
                if not wh.events:
                    with tag.div(classes="text-gray-500"):
                        text("No events subscribed")
                else:
                    with tag.div(classes="overflow-x-auto"):
                        with tag.table(classes="table table-zebra w-full"):
                            with tag.thead():
                                with tag.tr():
                                    with tag.th():
                                        text("Event Type")
                            with tag.tbody():
                                for evt in wh.events:
                                    with tag.tr():
                                        with tag.td():
                                            text(evt)


# ---------------------------------------------------------------------------
# List view
# ---------------------------------------------------------------------------


@router.get("/", name="webhooks:list")
async def list(
    request: Request,
    pagination: PaginationParamsQuery,
    query: str | None = Query(None),
    session: AsyncReadSession = Depends(get_db_read_session),
) -> None:
    admin_repo = AdminWebhookRepository.from_session(session)
    stmt = admin_repo.get_list_statement(query=query)

    items, count = await admin_repo.paginate(
        stmt, limit=pagination.limit, page=pagination.page
    )

    with layout(
        request,
        [("Webhooks", str(request.url_for("webhooks:list")))],
        "webhooks:list",
    ):
        with tag.div(classes="flex flex-col gap-4"):
            with tag.h1(classes="text-4xl"):
                text("Webhooks")

            with tag.form(method="GET", classes="w-full flex flex-row gap-2"):
                with input.search(
                    "query",
                    query,
                    placeholder="Search by ID, URL, workspace name/slug",
                ):
                    pass
                with button(type="submit"):
                    text("Filter")

            with datatable.Datatable[WebhookEndpoint, WebhookSortProperty](
                datatable.DatatableAttrColumn(
                    "id", "ID", href_route_name="webhooks:get", clipboard=True
                ),
                datatable.DatatableDateTimeColumn("created_at", "Created At"),
                datatable.DatatableAttrColumn("url", "URL"),
                datatable.DatatableAttrColumn("format", "Format"),
                datatable.DatatableAttrColumn("enabled", "Enabled"),
                datatable.DatatableAttrColumn(
                    "workspace.name",
                    "Workspace",
                    external_href=lambda r, i: str(
                        r.url_for("workspaces:get", id=i.workspace_id)
                    ),
                ),
            ).render(request, items):
                pass

            with datatable.pagination(request, pagination, count):
                pass


# ---------------------------------------------------------------------------
# Toggle enabled status
# ---------------------------------------------------------------------------


@router.get("/{id}/confirm-toggle-enabled", name="webhooks:confirm_toggle_enabled")
async def confirm_toggle_enabled(
    request: Request,
    id: UUID4,
    session: AsyncReadSession = Depends(get_db_read_session),
) -> None:
    repo = WebhookEndpointRepository.from_session(session)
    wh = await repo.get_by_id(id)

    if wh is None:
        raise HTTPException(status_code=404)

    verb = "disable" if wh.enabled else "enable"
    consequence = (
        "It will stop receiving events."
        if wh.enabled
        else "It will start receiving events again."
    )
    with confirmation_dialog(
        title=f"{verb.capitalize()} Webhook",
        message=f"Are you sure you want to {verb} this webhook endpoint? {consequence}",
        variant="warning",
        confirm_text=verb.capitalize(),
        open=True,
    ):
        attr(
            "hx-post",
            str(request.url_for("webhooks:toggle_enabled", id=wh.id)),
        )
        attr("hx-target", "#modal")


@router.post("/{id}/toggle-enabled", name="webhooks:toggle_enabled")
async def toggle_enabled(
    request: Request,
    id: UUID4,
    session: AsyncSession = Depends(get_db_session),
) -> None:
    repo = WebhookEndpointRepository.from_session(session)
    wh = await repo.get_by_id(id)

    if wh is None:
        raise HTTPException(status_code=404)

    new_state = not wh.enabled
    wh = await webhook_service.update_endpoint(
        session, endpoint=wh, update_schema=WebhookEndpointUpdate(enabled=new_state)
    )

    await add_toast(
        request,
        f"Webhook {'enabled' if wh.enabled else 'disabled'} successfully",
        "success",
    )

    with tag.div(id="modal"):
        pass

    with tag.div(id="webhook-details-list"):
        attr("hx-swap-oob", "true")
        with description_list.DescriptionList[WebhookEndpoint](
            description_list.DescriptionListAttrItem("id", "ID", clipboard=True),
            description_list.DescriptionListAttrItem("url", "URL"),
            description_list.DescriptionListAttrItem("format", "Format"),
            description_list.DescriptionListAttrItem("enabled", "Enabled"),
            description_list.DescriptionListDateTimeItem("created_at", "Created At"),
            description_list.DescriptionListDateTimeItem("modified_at", "Modified At"),
        ).render(request, wh):
            pass

    with tag.div(
        id="webhook-enabled-status",
        classes="flex items-center justify-between",
    ):
        attr("hx-swap-oob", "true")
        with tag.span(classes="label-text font-medium"):
            text("Enabled")
        with button(
            variant="success" if wh.enabled else "neutral",
            size="sm",
            hx_get=str(request.url_for("webhooks:confirm_toggle_enabled", id=wh.id)),
            hx_target="#modal",
        ):
            text("Enabled" if wh.enabled else "Disabled")
