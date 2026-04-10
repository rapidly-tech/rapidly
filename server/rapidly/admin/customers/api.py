"""Admin panel customer management routes (HTMX).

Server-rendered admin views for listing, inspecting, and editing
customer records, including wallet balances, event histories, and
associated member relationships.
"""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from pydantic import UUID4
from sqlalchemy.orm import joinedload
from tagflow import document, tag, text

from rapidly.config import settings
from rapidly.core.pagination import PaginationParamsQuery
from rapidly.customers.customer.queries import CustomerRepository
from rapidly.customers.customer_session.actions import (
    customer_session as customer_session_service,
)
from rapidly.models import Customer
from rapidly.postgres import (
    AsyncReadSession,
    AsyncSession,
    get_db_read_session,
    get_db_session,
)

from ..components import button, datatable, description_list, modal
from ..layout import layout
from .components import customers_datatable, email_verified_badge
from .queries import AdminCustomerRepository

router = APIRouter()


# ── List ──


@router.get("/", name="customers:list")
async def list(
    request: Request,
    pagination: PaginationParamsQuery,
    query: str | None = Query(None),
    session: AsyncReadSession = Depends(get_db_read_session),
) -> None:
    admin_repo = AdminCustomerRepository.from_session(session)
    stmt = admin_repo.get_list_statement(query=query)

    items, count = await admin_repo.paginate(
        stmt, limit=pagination.limit, page=pagination.page
    )

    with layout(
        request,
        [
            ("Customers", str(request.url_for("customers:list"))),
        ],
        "customers:list",
    ):
        with tag.div(classes="flex flex-col gap-4"):
            with tag.h1(classes="text-4xl"):
                text("Customers")
            with tag.form(method="GET", classes="w-full flex flex-row gap-2"):
                with tag.input(
                    type="search",
                    name="query",
                    value=query or "",
                    placeholder="Search by email, ID, external ID, or workspace...",
                    classes="input input-bordered flex-1",
                ):
                    pass
                with button(type="submit"):
                    text("Search")
            with customers_datatable(request, items):
                pass
            with datatable.pagination(request, pagination, count):
                pass


# ── Detail ──


@router.get("/{id}", name="customers:get")
async def get(
    request: Request,
    id: UUID4,
    session: AsyncReadSession = Depends(get_db_read_session),
) -> None:
    customer_repository = CustomerRepository.from_session(session)
    customer = await customer_repository.get_by_id(
        id,
        options=(joinedload(Customer.workspace),),
    )

    if customer is None:
        raise HTTPException(status_code=404)

    with layout(
        request,
        [
            (customer.email, str(request.url)),
            ("Customers", str(request.url_for("customers:list"))),
        ],
        "customers:get",
    ):
        with tag.div(classes="flex flex-col gap-4"):
            with tag.div(classes="flex justify-between items-center"):
                with tag.h1(classes="text-4xl"):
                    text(customer.email)
                with button(
                    hx_get=str(
                        request.url_for(
                            "customers:generate_portal_link_modal", id=customer.id
                        )
                    ),
                    hx_target="#modal",
                    variant="primary",
                ):
                    text("Generate Portal Link")

            with tag.div(classes="grid grid-cols-1 lg:grid-cols-2 gap-4"):
                # Customer Details
                with tag.div(classes="card card-border w-full shadow-sm"):
                    with tag.div(classes="card-body"):
                        with tag.h2(classes="card-title"):
                            text("Customer Details")
                        with description_list.DescriptionList[Customer](
                            description_list.DescriptionListAttrItem(
                                "id", "ID", clipboard=True
                            ),
                            description_list.DescriptionListAttrItem(
                                "email", "Email", clipboard=True
                            ),
                            description_list.DescriptionListAttrItem("name", "Name"),
                            description_list.DescriptionListAttrItem(
                                "external_id", "External ID", clipboard=True
                            ),
                            description_list.DescriptionListDateTimeItem(
                                "created_at", "Created At"
                            ),
                        ).render(request, customer):
                            pass

                # Workspace
                with tag.div(classes="card card-border w-full shadow-sm"):
                    with tag.div(classes="card-body"):
                        with tag.h2(classes="card-title"):
                            text("Workspace")
                        with description_list.DescriptionList[Customer](
                            description_list.DescriptionListLinkItem[Customer](
                                "workspace.name",
                                "Name",
                                href_getter=lambda r, i: str(
                                    r.url_for("workspaces:get", id=i.workspace_id)
                                ),
                            ),
                            description_list.DescriptionListAttrItem(
                                "workspace.slug", "Slug"
                            ),
                        ).render(request, customer):
                            pass

                # Billing Information
                with tag.div(classes="card card-border w-full shadow-sm"):
                    with tag.div(classes="card-body"):
                        with tag.h2(classes="card-title"):
                            text("Billing Information")
                        with description_list.DescriptionList[Customer](
                            description_list.DescriptionListAttrItem(
                                "billing_name", "Billing Name"
                            ),
                        ).render(request, customer):
                            pass

                        if customer.billing_address:
                            with tag.div(classes="mt-4"):
                                with tag.h3(classes="text-lg font-semibold mb-2"):
                                    text("Billing Address")
                                with description_list.DescriptionList[Customer](
                                    description_list.DescriptionListAttrItem(
                                        "billing_address.line1", "Address Line 1"
                                    ),
                                    description_list.DescriptionListAttrItem(
                                        "billing_address.line2", "Address Line 2"
                                    ),
                                    description_list.DescriptionListAttrItem(
                                        "billing_address.city", "City"
                                    ),
                                    description_list.DescriptionListAttrItem(
                                        "billing_address.state", "State"
                                    ),
                                    description_list.DescriptionListAttrItem(
                                        "billing_address.postal_code", "Postal Code"
                                    ),
                                    description_list.DescriptionListAttrItem(
                                        "billing_address.country", "Country"
                                    ),
                                ).render(request, customer):
                                    pass

                # Stripe Information
                with tag.div(classes="card card-border w-full shadow-sm"):
                    with tag.div(classes="card-body"):
                        with tag.h2(classes="card-title"):
                            text("Stripe Information")
                        if customer.stripe_customer_id:
                            with description_list.DescriptionList[Customer](
                                description_list.DescriptionListLinkItem[Customer](
                                    "stripe_customer_id",
                                    "Stripe Customer ID",
                                    href_getter=lambda _, i: (
                                        f"https://dashboard.stripe.com/customers/{i.stripe_customer_id}"
                                    ),
                                    external=True,
                                ),
                            ).render(request, customer):
                                pass
                        else:
                            with tag.p(classes="text-gray-500"):
                                text("No Stripe customer linked")

                        with tag.div(classes="mt-4"):
                            with tag.div(classes="flex items-center gap-2"):
                                with tag.span(classes="font-semibold"):
                                    text("Email Verified:")
                                with email_verified_badge(customer.email_verified):
                                    pass


@router.get(
    "/{id}/generate_portal_link_modal", name="customers:generate_portal_link_modal"
)
async def generate_portal_link_modal(
    request: Request,
    id: UUID4,
    session: AsyncSession = Depends(get_db_session),
) -> Any:
    customer_repository = CustomerRepository.from_session(session)
    customer = await customer_repository.get_by_id(
        id, options=(joinedload(Customer.workspace),)
    )

    if customer is None:
        raise HTTPException(status_code=404)

    if not customer.workspace:
        raise HTTPException(
            status_code=500, detail="Customer workspace not properly loaded"
        )

    # Generate customer session token
    token, customer_session = await customer_session_service.create_customer_session(
        session, customer
    )

    # Construct portal URL with workspace slug
    frontend_base_url = str(settings.FRONTEND_BASE_URL).rstrip("/")
    org_slug = customer.workspace.slug
    portal_url = (
        f"{frontend_base_url}/{org_slug}/portal/overview?customer_session_token={token}"
    )

    # Calculate actual expiration time from settings
    expires_in_hours = int(settings.CUSTOMER_SESSION_TTL.total_seconds() / 3600)
    if expires_in_hours < 1:
        expires_in_minutes = int(settings.CUSTOMER_SESSION_TTL.total_seconds() / 60)
        expiration_message = f"{expires_in_minutes} minutes"
    else:
        expiration_message = (
            f"{expires_in_hours} hour{'s' if expires_in_hours != 1 else ''}"
        )

    with document() as doc:
        with tag.div(id="modal"):
            with modal("Customer Portal Link Generated", open=True):
                with tag.div(classes="alert alert-info mb-4"):
                    with tag.div():
                        with tag.p(classes="text-sm"):
                            text(
                                f"This link will expire in {expiration_message}. "
                                "The customer can use this link to access their portal."
                            )

                with tag.div(classes="form-control w-full mb-4"):
                    with tag.label(classes="label"):
                        with tag.span(classes="label-text font-semibold"):
                            text("Portal URL")
                    with tag.div(classes="flex gap-2 items-center"):
                        with tag.input(
                            type="text",
                            value=portal_url,
                            readonly=True,
                            classes="input input-bordered flex-1 font-mono text-sm",
                        ):
                            pass
                        with tag.a(
                            href=portal_url,
                            target="_blank",
                            rel="noopener noreferrer",
                            classes="btn btn-primary",
                        ):
                            text("Open Portal")

                with tag.div(classes="modal-action"):
                    with tag.form(method="dialog"):
                        with button(variant="primary"):
                            text("Done")

    return HTMLResponse(str(doc))
