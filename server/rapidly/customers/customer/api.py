"""Customer HTTP routes: CRUD, CSV export, state queries, and member linking.

Supports creating, listing, updating, and deleting customers within an
workspace.  Includes a streaming CSV export endpoint and the ability
to associate members with a customer record.
"""

import json
import uuid
from collections.abc import AsyncGenerator

from fastapi import Depends, Query, Response
from fastapi.responses import StreamingResponse

from rapidly.core.csv import IterableCSVWriter
from rapidly.core.metadata import MetadataQuery, get_metadata_query_openapi_schema
from rapidly.core.pagination import PaginatedList, PaginationParamsQuery
from rapidly.core.types import MultipleQueryFilter
from rapidly.errors import ResourceNotFound
from rapidly.identity.member.types import Member as MemberSchema
from rapidly.models import Customer
from rapidly.openapi import APITag
from rapidly.platform.workspace.types import WorkspaceID
from rapidly.postgres import (
    AsyncReadSession,
    AsyncSession,
    get_db_read_session,
    get_db_session,
)
from rapidly.redis import Redis, get_redis
from rapidly.routing import APIRouter

from . import actions as customer_service
from . import ordering
from . import permissions as auth
from .types.customer import Customer as CustomerSchema
from .types.customer import (
    CustomerCreate,
    CustomerID,
    CustomerUpdate,
    CustomerUpdateExternalID,
    CustomerWithMembers,
    ExternalCustomerID,
)
from .types.state import CustomerState


async def _to_customer_with_members(
    session: AsyncReadSession,
    customer: Customer,
    include_members: bool,
) -> CustomerWithMembers:
    """Convert a Customer model to CustomerWithMembers schema."""
    customer_dict = CustomerSchema.model_validate(customer).model_dump()
    if include_members:
        customer_dict["members"] = await customer_service.load_members(
            session, customer.id
        )
    else:
        customer_dict["members"] = []
    return CustomerWithMembers(**customer_dict)


router = APIRouter(
    prefix="/customers",
    tags=["customers", APITag.public, APITag.mcp],
)


CustomerNotFound = {
    "description": "Customer not found.",
    "model": ResourceNotFound.schema(),
}


# ── List & Export ──


@router.get(
    "/",
    summary="List Customers",
    response_model=PaginatedList[CustomerWithMembers],
    openapi_extra={"parameters": [get_metadata_query_openapi_schema()]},
)
async def list_customers_endpoint(
    auth_subject: auth.CustomerRead,
    pagination: PaginationParamsQuery,
    sorting: ordering.ListSorting,
    metadata: MetadataQuery,
    workspace_id: MultipleQueryFilter[WorkspaceID] | None = Query(
        None, title="WorkspaceID Filter", description="Filter by workspace ID."
    ),
    email: str | None = Query(None, description="Filter by exact email."),
    query: str | None = Query(
        None, description="Filter by name, email, or external ID."
    ),
    include_members: bool = Query(
        False,
        description="Include members in the response. Only populated when set to true.",
        include_in_schema=False,
    ),
    session: AsyncReadSession = Depends(get_db_read_session),
) -> PaginatedList[CustomerWithMembers]:
    """List customers."""
    results, count = await customer_service.list_customers(
        session,
        auth_subject,
        workspace_id=workspace_id,
        email=email,
        metadata=metadata,
        query=query,
        pagination=pagination,
        sorting=sorting,
    )

    members_by_customer: dict[uuid.UUID, list[MemberSchema]] = {}
    if include_members and results:
        members_by_customer = await customer_service.batch_load_members(
            session, [r.id for r in results]
        )

    customers_with_members = []
    for result in results:
        customer_dict = CustomerSchema.model_validate(result).model_dump()
        customer_dict["members"] = members_by_customer.get(result.id, [])
        customers_with_members.append(CustomerWithMembers(**customer_dict))

    return PaginatedList.from_paginated_results(
        customers_with_members,
        count,
        pagination,
    )


@router.get("/export", summary="Export Customers")
async def export(
    auth_subject: auth.CustomerRead,
    workspace_id: MultipleQueryFilter[WorkspaceID] | None = Query(
        None, description="Filter by workspace ID."
    ),
    session: AsyncReadSession = Depends(get_db_read_session),
) -> Response:
    """Export customers as a CSV file."""

    async def create_csv() -> AsyncGenerator[str, None]:
        csv_writer = IterableCSVWriter(dialect="excel")

        yield csv_writer.getrow(
            (
                "ID",
                "External ID",
                "Created At",
                "Email",
                "Name",
                "Billing Address Line 1",
                "Billing Address Line 2",
                "Billing Address City",
                "Billing Address State",
                "Billing Address Zip",
                "Billing Address Country",
                "Metadata",
            )
        )

        stream = customer_service.stream_for_export(
            session, auth_subject, workspace_id=workspace_id
        )

        async for customer in stream:
            billing_address = customer.billing_address

            yield csv_writer.getrow(
                (
                    customer.id,
                    customer.external_id,
                    customer.created_at.isoformat(),
                    customer.email,
                    customer.name,
                    billing_address.line1 if billing_address else None,
                    billing_address.line2 if billing_address else None,
                    billing_address.city if billing_address else None,
                    billing_address.state if billing_address else None,
                    billing_address.postal_code if billing_address else None,
                    billing_address.country if billing_address else None,
                    json.dumps(customer.user_metadata)
                    if customer.user_metadata
                    else None,
                )
            )

    filename = "rapidly-customers.csv"
    return StreamingResponse(
        create_csv(),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


# ── Retrieval ──


@router.get(
    "/{id}",
    summary="Get Customer",
    response_model=CustomerWithMembers,
    responses={404: CustomerNotFound},
)
async def get(
    id: CustomerID,
    auth_subject: auth.CustomerRead,
    include_members: bool = Query(
        False,
        description="Include members in the response. Only populated when set to true.",
        include_in_schema=False,
    ),
    session: AsyncReadSession = Depends(get_db_read_session),
) -> CustomerWithMembers:
    """Get a customer by ID."""
    customer = await customer_service.get(session, auth_subject, id)

    if customer is None:
        raise ResourceNotFound()

    return await _to_customer_with_members(session, customer, include_members)


@router.get(
    "/external/{external_id}",
    summary="Get Customer by External ID",
    response_model=CustomerWithMembers,
    responses={404: CustomerNotFound},
)
async def get_external(
    external_id: ExternalCustomerID,
    auth_subject: auth.CustomerRead,
    include_members: bool = Query(
        False,
        description="Include members in the response. Only populated when set to true.",
        include_in_schema=False,
    ),
    session: AsyncReadSession = Depends(get_db_read_session),
) -> CustomerWithMembers:
    """Get a customer by external ID."""
    customer = await customer_service.get_external(session, auth_subject, external_id)

    if customer is None:
        raise ResourceNotFound()

    return await _to_customer_with_members(session, customer, include_members)


# ── State ──


@router.get(
    "/{id}/state",
    summary="Get Customer State",
    response_model=CustomerState,
    responses={404: CustomerNotFound},
)
async def get_state(
    id: CustomerID,
    auth_subject: auth.CustomerRead,
    session: AsyncReadSession = Depends(get_db_read_session),
    redis: Redis = Depends(get_redis),
) -> CustomerState:
    """
    Get a customer state by ID.

    The customer state includes information about
    the customer's active meters.

    It's the ideal endpoint to use when you need to get a full overview
    of a customer's status.
    """
    customer = await customer_service.get(session, auth_subject, id)

    if customer is None:
        raise ResourceNotFound()

    return await customer_service.get_state(session, redis, customer)


@router.get(
    "/external/{external_id}/state",
    summary="Get Customer State by External ID",
    response_model=CustomerState,
    responses={404: CustomerNotFound},
)
async def get_state_external(
    external_id: ExternalCustomerID,
    auth_subject: auth.CustomerRead,
    session: AsyncReadSession = Depends(get_db_read_session),
    redis: Redis = Depends(get_redis),
) -> CustomerState:
    """
    Get a customer state by external ID.

    The customer state includes information about
    the customer's active meters.

    It's the ideal endpoint to use when you need to get a full overview
    of a customer's status.
    """
    customer = await customer_service.get_external(session, auth_subject, external_id)

    if customer is None:
        raise ResourceNotFound()

    return await customer_service.get_state(session, redis, customer)


# ── Create & Update ──


@router.post(
    "/",
    response_model=CustomerWithMembers,
    status_code=201,
    summary="Create Customer",
    responses={201: {"description": "Customer created."}},
)
async def create(
    customer_create: CustomerCreate,
    auth_subject: auth.CustomerWrite,
    include_members: bool = Query(
        False,
        description="Include members in the response. Only populated when set to true.",
        include_in_schema=False,
    ),
    session: AsyncSession = Depends(get_db_session),
) -> CustomerWithMembers:
    """Create a customer."""
    created_customer = await customer_service.create(
        session, customer_create, auth_subject
    )

    customer = await customer_service.get_by_id(session, created_customer.id)
    if customer is None:
        raise ResourceNotFound()

    return await _to_customer_with_members(session, customer, include_members)


@router.patch(
    "/{id}",
    response_model=CustomerWithMembers,
    summary="Update Customer",
    responses={
        200: {"description": "Customer updated."},
        404: CustomerNotFound,
    },
)
async def update(
    id: CustomerID,
    customer_update: CustomerUpdate,
    auth_subject: auth.CustomerWrite,
    include_members: bool = Query(
        False,
        description="Include members in the response. Only populated when set to true.",
        include_in_schema=False,
    ),
    session: AsyncSession = Depends(get_db_session),
) -> CustomerWithMembers:
    """Update a customer."""
    customer = await customer_service.get(session, auth_subject, id)

    if customer is None:
        raise ResourceNotFound()

    updated_customer = await customer_service.update(session, customer, customer_update)

    return await _to_customer_with_members(session, updated_customer, include_members)


@router.patch(
    "/external/{external_id}",
    response_model=CustomerWithMembers,
    summary="Update Customer by External ID",
    responses={
        200: {"description": "Customer updated."},
        404: CustomerNotFound,
    },
)
async def update_external(
    external_id: ExternalCustomerID,
    customer_update: CustomerUpdateExternalID,
    auth_subject: auth.CustomerWrite,
    include_members: bool = Query(
        False,
        description="Include members in the response. Only populated when set to true.",
        include_in_schema=False,
    ),
    session: AsyncSession = Depends(get_db_session),
) -> CustomerWithMembers:
    """Update a customer by external ID."""
    customer = await customer_service.get_external(session, auth_subject, external_id)

    if customer is None:
        raise ResourceNotFound()

    updated_customer = await customer_service.update(session, customer, customer_update)

    return await _to_customer_with_members(session, updated_customer, include_members)


# ── Deletion ──


@router.delete(
    "/{id}",
    status_code=204,
    summary="Delete Customer",
    responses={
        204: {"description": "Customer deleted."},
        404: CustomerNotFound,
    },
)
async def delete(
    id: CustomerID,
    auth_subject: auth.CustomerWrite,
    anonymize: bool = Query(
        default=False,
        description=(
            "If true, also anonymize the customer's personal data for GDPR compliance. "
            "This replaces email with a hashed version, hashes name and billing name, "
            "clears billing address, and removes OAuth account data."
        ),
    ),
    session: AsyncSession = Depends(get_db_session),
) -> None:
    """
    Delete a customer.

    This action cannot be undone and will immediately:
    - Soft-delete the customer record
    - Clear any `external_id`

    Set `anonymize=true` to also anonymize PII for GDPR compliance.
    """
    customer = await customer_service.get(session, auth_subject, id)

    if customer is None:
        raise ResourceNotFound()

    await customer_service.delete(session, customer, anonymize=anonymize)


@router.delete(
    "/external/{external_id}",
    status_code=204,
    summary="Delete Customer by External ID",
    responses={
        204: {"description": "Customer deleted."},
        404: CustomerNotFound,
    },
)
async def delete_external(
    external_id: ExternalCustomerID,
    auth_subject: auth.CustomerWrite,
    anonymize: bool = Query(
        default=False,
        description=(
            "If true, also anonymize the customer's personal data for GDPR compliance."
        ),
    ),
    session: AsyncSession = Depends(get_db_session),
) -> None:
    """
    Delete a customer by external ID.

    Soft-deletes the customer record.

    Set `anonymize=true` to also anonymize PII for GDPR compliance.
    """
    customer = await customer_service.get_external(session, auth_subject, external_id)

    if customer is None:
        raise ResourceNotFound()

    await customer_service.delete(session, customer, anonymize=anonymize)
