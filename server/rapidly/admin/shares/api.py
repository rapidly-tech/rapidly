"""Admin panel share management (HTMX).

Server-rendered views for listing products across workspaces,
inspecting share details, prices, and related metadata.
"""

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import UUID4
from sqlalchemy.orm import joinedload, selectinload
from tagflow import tag, text

from rapidly.catalog.share import ordering
from rapidly.catalog.share.guard import (
    is_custom_price,
    is_fixed_price,
    is_free_price,
)
from rapidly.catalog.share.ordering import ShareSortProperty
from rapidly.catalog.share.queries import ShareRepository
from rapidly.core.pagination import PaginationParamsQuery
from rapidly.models import Share
from rapidly.models.share_price import SharePrice
from rapidly.postgres import AsyncReadSession, get_db_read_session

from .. import formatters
from ..components import button, datatable, description_list, input
from ..layout import layout
from .queries import AdminShareRepository

router = APIRouter()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _render_price(price: SharePrice) -> str:
    """Format a price for display based on its amount type."""
    if is_free_price(price):
        return "Free"

    if is_custom_price(price):
        details: list[str] = []
        if price.minimum_amount is not None:
            details.append(
                f"Min: {formatters.currency(price.minimum_amount, price.price_currency)}"
            )
        if price.maximum_amount is not None:
            details.append(
                f"Max: {formatters.currency(price.maximum_amount, price.price_currency)}"
            )
        if price.preset_amount is not None:
            details.append(
                f"Preset: {formatters.currency(price.preset_amount, price.price_currency)}"
            )
        suffix = f" ({', '.join(details)})" if details else ""
        return f"Pay what you want{suffix}"

    if is_fixed_price(price):
        return formatters.currency(price.price_amount, price.price_currency)

    return "N/A"


class WorkspaceColumn(datatable.DatatableAttrColumn[Share, ShareSortProperty]):
    def __init__(self) -> None:
        super().__init__("workspace.name", "Workspace")
        self.href_getter = lambda r, i: str(
            r.url_for("workspaces:get", id=i.workspace_id)
        )


# ---------------------------------------------------------------------------
# Detail view
# ---------------------------------------------------------------------------


@router.get("/{id}", name="shares:get")
async def get(
    request: Request,
    id: UUID4,
    session: AsyncReadSession = Depends(get_db_read_session),
) -> None:
    repo = ShareRepository.from_session(session)
    share = await repo.get_by_id(
        id,
        options=(
            joinedload(Share.workspace),
            selectinload(Share.all_prices),
        ),
    )

    if share is None:
        raise HTTPException(status_code=404)

    with layout(
        request,
        [
            (f"{share.name}", str(request.url)),
            ("Products", str(request.url_for("shares:list"))),
        ],
        "shares:get",
    ):
        with tag.div(classes="flex flex-col gap-4"):
            with tag.div(classes="flex justify-between items-center"):
                with tag.h1(classes="text-4xl"):
                    text(f"Share: {share.name}")

            with tag.div(classes="grid grid-cols-1 lg:grid-cols-2 gap-4"):
                # Share details card
                with tag.div(classes="card card-border w-full shadow-sm"):
                    with tag.div(classes="card-body"):
                        with tag.h2(classes="card-title"):
                            text("Share Details")
                        with description_list.DescriptionList[Share](
                            description_list.DescriptionListAttrItem(
                                "id", "ID", clipboard=True
                            ),
                            description_list.DescriptionListAttrItem("name", "Name"),
                            description_list.DescriptionListAttrItem(
                                "description", "Description"
                            ),
                            description_list.DescriptionListAttrItem(
                                "is_archived", "Archived"
                            ),
                            description_list.DescriptionListDateTimeItem(
                                "created_at", "Created At"
                            ),
                            description_list.DescriptionListDateTimeItem(
                                "modified_at", "Modified At"
                            ),
                        ).render(request, share):
                            pass

                # Workspace card
                with tag.div(classes="card card-border w-full shadow-sm"):
                    with tag.div(classes="card-body"):
                        with tag.h2(classes="card-title"):
                            text("Workspace")
                        with description_list.DescriptionList[Share](
                            description_list.DescriptionListLinkItem[Share](
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
                        ).render(request, share):
                            pass

            # Prices table
            with tag.div(classes="flex flex-col gap-4 pt-8"):
                with tag.h2(classes="text-2xl"):
                    text("Prices")
                if not share.all_prices:
                    with tag.div(classes="text-gray-500"):
                        text("No prices configured for this share.")
                else:
                    with tag.div(classes="overflow-x-auto"):
                        with tag.table(classes="table table-zebra w-full"):
                            with tag.thead():
                                with tag.tr():
                                    with tag.th():
                                        text("ID")
                                    with tag.th():
                                        text("Amount Type")
                                    with tag.th():
                                        text("Price")
                                    with tag.th():
                                        text("Archived")
                            with tag.tbody():
                                for p in share.all_prices:
                                    with tag.tr():
                                        with tag.td():
                                            text(str(p.id))
                                        with tag.td():
                                            text(
                                                p.amount_type.replace("_", " ").title()
                                            )
                                        with tag.td():
                                            text(_render_price(p))
                                        with tag.td():
                                            text(str(p.is_archived))


# ---------------------------------------------------------------------------
# List view
# ---------------------------------------------------------------------------


@router.get("/", name="shares:list")
async def list_shares(
    request: Request,
    pagination: PaginationParamsQuery,
    sorting: ordering.ListSorting,
    query: str | None = Query(None),
    session: AsyncReadSession = Depends(get_db_read_session),
) -> None:
    admin_repo = AdminShareRepository.from_session(session)
    stmt = admin_repo.get_list_statement(query=query)

    domain_repo = ShareRepository.from_session(session)
    stmt = domain_repo.apply_sorting(stmt, sorting)

    items, count = await admin_repo.paginate(
        stmt, limit=pagination.limit, page=pagination.page
    )

    with layout(
        request,
        [("Products", str(request.url_for("shares:list")))],
        "shares:list",
    ):
        with tag.div(classes="flex flex-col gap-4"):
            with tag.h1(classes="text-4xl"):
                text("Products")

            with tag.form(method="GET", classes="w-full flex flex-row gap-2"):
                with input.search(
                    "query",
                    query,
                    placeholder="Search by ID, name, workspace name/slug",
                ):
                    pass
                with button(type="submit"):
                    text("Filter")

            with datatable.Datatable[Share, ShareSortProperty](
                datatable.DatatableAttrColumn(
                    "id", "ID", href_route_name="shares:get", clipboard=True
                ),
                datatable.DatatableDateTimeColumn(
                    "created_at",
                    "Created At",
                    sorting=ShareSortProperty.created_at,
                ),
                datatable.DatatableAttrColumn(
                    "name", "Name", sorting=ShareSortProperty.product_name
                ),
                WorkspaceColumn(),
                datatable.DatatableAttrColumn("is_archived", "Archived"),
            ).render(request, items, sorting=sorting):
                pass

            with datatable.pagination(request, pagination, count):
                pass
