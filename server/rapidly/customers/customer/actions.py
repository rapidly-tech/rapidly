"""Customer CRUD, metadata management, and webhook dispatch."""

import uuid
from collections.abc import AsyncGenerator, Sequence
from datetime import timedelta
from typing import Any

from sqlalchemy.exc import IntegrityError

from rapidly.core.anonymization import (
    ANONYMIZED_EMAIL_DOMAIN,
    anonymize_email_for_deletion,
    anonymize_for_deletion,
)
from rapidly.core.metadata import MetadataQuery
from rapidly.core.ordering import Sorting
from rapidly.core.pagination import PaginationParams
from rapidly.core.utils import now_utc
from rapidly.errors import RequestValidationError, ValidationError, validation_error
from rapidly.identity.auth.models import AuthPrincipal
from rapidly.identity.member import member_service
from rapidly.identity.member.types import Member as MemberSchema
from rapidly.messaging.webhook import actions as webhook_service
from rapidly.models import Customer, User, Workspace
from rapidly.models.customer import CustomerType
from rapidly.models.webhook_endpoint import CustomerWebhookEventType, WebhookEventType
from rapidly.platform.workspace.resolver import get_payload_workspace
from rapidly.postgres import AsyncReadSession, AsyncSession
from rapidly.redis import Redis

from .ordering import CustomerSortProperty
from .queries import CustomerRepository
from .types.customer import (
    CustomerCreate,
    CustomerUpdate,
    CustomerUpdateExternalID,
)
from .types.state import CustomerState

# ── Reads ──


async def list_customers(
    session: AsyncReadSession,
    auth_subject: AuthPrincipal[User | Workspace],
    *,
    workspace_id: Sequence[uuid.UUID] | None = None,
    email: str | None = None,
    metadata: MetadataQuery | None = None,
    query: str | None = None,
    pagination: PaginationParams,
    sorting: Sequence[Sorting[CustomerSortProperty]] = (
        (CustomerSortProperty.created_at, True),
    ),
) -> tuple[Sequence[Customer], int]:
    repository = CustomerRepository.from_session(session)
    statement = repository.get_readable_statement(auth_subject)
    statement = repository.apply_list_filters(
        statement,
        workspace_id=workspace_id,
        email=email,
        metadata=metadata,
        query=query,
        sorting=sorting,
    )
    return await repository.paginate(
        statement, limit=pagination.limit, page=pagination.page
    )


async def get(
    session: AsyncReadSession,
    auth_subject: AuthPrincipal[User | Workspace],
    id: uuid.UUID,
) -> Customer | None:
    repository = CustomerRepository.from_session(session)
    statement = repository.get_readable_statement(auth_subject).where(Customer.id == id)
    return await repository.get_one_or_none(statement)


async def get_by_id(
    session: AsyncReadSession,
    id: uuid.UUID,
) -> Customer | None:
    """Fetch a customer by primary key without auth scoping."""
    repository = CustomerRepository.from_session(session)
    return await repository.get_by_id(id)


async def stream_for_export(
    session: AsyncReadSession,
    auth_subject: AuthPrincipal[User | Workspace],
    *,
    workspace_id: Sequence[uuid.UUID] | None = None,
) -> "AsyncGenerator[Customer]":
    """Stream customers for CSV export."""
    repository = CustomerRepository.from_session(session)
    async for customer in repository.stream_by_workspace(auth_subject, workspace_id):
        yield customer


async def get_external(
    session: AsyncReadSession,
    auth_subject: AuthPrincipal[User | Workspace],
    external_id: str,
) -> Customer | None:
    repository = CustomerRepository.from_session(session)
    statement = repository.get_readable_statement(auth_subject).where(
        Customer.external_id == external_id
    )
    return await repository.get_one_or_none(statement)


async def get_or_create_by_email(
    session: AsyncSession,
    *,
    email: str,
    workspace_id: uuid.UUID,
    name: str | None = None,
) -> Customer:
    """Look up a customer by email + workspace, creating one if not found.

    Used by file sharing payment flow where we don't have a full
    CustomerCreate schema or auth subject.
    """
    repository = CustomerRepository.from_session(session)
    existing = await repository.get_by_email_and_workspace(email, workspace_id)
    if existing is not None:
        return existing

    from rapidly.platform.workspace.queries import WorkspaceRepository

    org_repo = WorkspaceRepository.from_session(session)
    workspace = await org_repo.get_by_id(workspace_id)
    if workspace is None:
        raise ValueError(f"Workspace {workspace_id} not found")

    try:
        async with session.begin_nested():
            async with repository.create_context(
                Customer(
                    email=email,
                    name=name,
                    workspace=workspace,
                )
            ) as new_customer:
                return new_customer
    except IntegrityError:
        # Race condition: another transaction created this customer concurrently.
        # Re-fetch the existing record.
        existing = await repository.get_by_email_and_workspace(email, workspace_id)
        if existing is not None:
            return existing
        raise


# ── Writes ──


async def create(
    session: AsyncSession,
    customer_create: CustomerCreate,
    auth_subject: AuthPrincipal[User | Workspace],
) -> Customer:
    workspace = await get_payload_workspace(session, auth_subject, customer_create)
    repository = CustomerRepository.from_session(session)

    errors: list[ValidationError] = []

    if await repository.get_by_email_and_workspace(customer_create.email, workspace.id):
        errors.append(
            validation_error(
                "email",
                "A customer with this email address already exists.",
                customer_create.email,
            )
        )

    if customer_create.external_id is not None:
        if await repository.get_by_external_id_and_workspace(
            customer_create.external_id, workspace.id
        ):
            errors.append(
                validation_error(
                    "external_id",
                    "A customer with this external ID already exists.",
                    customer_create.external_id,
                )
            )

    if errors:
        raise RequestValidationError(errors)

    try:
        async with repository.create_context(
            Customer(
                workspace=workspace,
                **customer_create.model_dump(
                    exclude={"workspace_id", "owner"}, by_alias=True
                ),
            ),
            flush=True,
        ) as customer:
            owner_email = customer_create.owner.email if customer_create.owner else None
            owner_name = customer_create.owner.name if customer_create.owner else None
            owner_external_id = (
                customer_create.owner.external_id if customer_create.owner else None
            )

            await member_service.create_owner_member(
                session,
                customer,
                workspace,
                owner_email=owner_email,
                owner_name=owner_name,
                owner_external_id=owner_external_id,
            )
            return customer
    except IntegrityError as exc:
        # Race condition: another transaction committed between our check
        # and the INSERT.  Convert to a user-facing validation error.
        await session.rollback()
        # Check constraint name from the original DBAPI error
        constraint = getattr(exc.orig, "constraint_name", None)
        if constraint is None:
            # asyncpg wraps the constraint name in the message
            constraint = str(exc.orig) if exc.orig else str(exc)
        if "external_id" in constraint:
            field, detail = (
                "external_id",
                "A customer with this external ID already exists.",
            )
        elif "email" in constraint:
            field, detail = (
                "email",
                "A customer with this email address already exists.",
            )
        else:
            raise
        raise RequestValidationError(
            [validation_error(field, detail, getattr(customer_create, field, None))]
        ) from exc


async def update(
    session: AsyncSession,
    customer: Customer,
    customer_update: CustomerUpdate | CustomerUpdateExternalID,
) -> Customer:
    repository = CustomerRepository.from_session(session)

    errors: list[ValidationError] = []
    if (
        customer_update.email is not None
        and customer.email.lower() != customer_update.email.lower()
    ):
        already_exists = await repository.get_by_email_and_workspace(
            customer_update.email, customer.workspace_id
        )
        if already_exists:
            errors.append(
                validation_error(
                    "email",
                    "A customer with this email address already exists.",
                    customer_update.email,
                )
            )

        customer.email = customer_update.email
        customer.email_verified = False

    # Validate external_id changes (only for CustomerUpdate schema)
    if (
        isinstance(customer_update, CustomerUpdate)
        and "external_id" in customer_update.model_fields_set
        and customer.external_id != customer_update.external_id
    ):
        if customer.external_id is not None:
            # external_id was already set - cannot be changed
            errors.append(
                validation_error(
                    "external_id",
                    "Customer external ID cannot be updated.",
                    customer_update.external_id,
                )
            )
        elif (
            customer_update.external_id is not None
            and await repository.get_by_external_id_and_workspace(
                customer_update.external_id, customer.workspace_id
            )
        ):
            # Setting new external_id that already exists
            errors.append(
                validation_error(
                    "external_id",
                    "A customer with this external ID already exists.",
                    customer_update.external_id,
                )
            )

    # Prevent downgrade from team to individual
    # NULL type is treated as 'individual' (legacy customers)
    current_type = customer.type or CustomerType.individual
    if (
        isinstance(customer_update, CustomerUpdate)
        and customer_update.type is not None
        and current_type == CustomerType.team
        and customer_update.type == CustomerType.individual
    ):
        errors.append(
            validation_error(
                "type",
                "Customer type cannot be downgraded from 'team' to 'individual'.",
                customer_update.type,
            )
        )

    if errors:
        raise RequestValidationError(errors)

    return await repository.update(
        customer,
        update_dict=customer_update.model_dump(
            exclude={"email"}, exclude_unset=True, by_alias=True
        ),
    )


# ── Deletion ──


async def delete(
    session: AsyncSession,
    customer: Customer,
    *,
    anonymize: bool = False,
) -> Customer:
    if anonymize:
        # Anonymize also sets deleted_at
        return await anonymize_customer(session, customer)

    repository = CustomerRepository.from_session(session)
    return await repository.soft_delete(customer)


async def anonymize_customer(
    session: AsyncSession,
    customer: Customer,
) -> Customer:
    """
    Anonymize customer PII for GDPR compliance.

    This anonymizes personal data while:
    - Preserving the Stripe customer ID for payment history
    - Preserving external_id for legal reasons

    This is idempotent - calling it on an already-anonymized customer
    will return success without making changes.
    """
    # Skip if already anonymized (idempotent)
    if customer.email.endswith(f"@{ANONYMIZED_EMAIL_DOMAIN}"):
        return customer

    repository = CustomerRepository.from_session(session)
    update_dict: dict[str, Any] = {}

    # Anonymize email (always)
    update_dict["email"] = anonymize_email_for_deletion(customer.email)
    update_dict["email_verified"] = False

    # Anonymize name
    if customer.name:
        update_dict["name"] = anonymize_for_deletion(customer.name)

    # Anonymize billing_name (always, if present)
    if customer._billing_name:
        update_dict["_billing_name"] = anonymize_for_deletion(customer._billing_name)

    # Clear address (invoices retain original)
    update_dict["billing_address"] = None

    # Clear OAuth tokens
    update_dict["_oauth_accounts"] = {}

    # Mark as deleted (soft-delete)
    update_dict["deleted_at"] = now_utc()

    # Record anonymization timestamp in metadata
    user_metadata = dict(customer.user_metadata) if customer.user_metadata else {}
    user_metadata["__anonymized_at"] = now_utc().isoformat()
    update_dict["user_metadata"] = user_metadata

    # NOTE: external_id is RETAINED for legal reasons

    # The repository.update() method automatically enqueues the webhook job
    customer = await repository.update(customer, update_dict=update_dict)

    return customer


# ── State & Webhooks ──


async def get_state(
    session: AsyncReadSession,
    redis: Redis,
    customer: Customer,
    cache: bool = True,
) -> CustomerState:
    # 👋 Whenever you change the state schema,
    # please also update the cache key with a version number.
    cache_key = f"rapidly:customer_state:v4:{customer.id}"

    if cache:
        raw_state = await redis.get(cache_key)
        if raw_state is not None:
            return CustomerState.model_validate_json(raw_state)

    state = CustomerState.model_validate(customer)

    await redis.set(
        cache_key,
        state.model_dump_json(),
        ex=int(timedelta(hours=1).total_seconds()),
    )

    return state


async def webhook(
    session: AsyncSession,
    redis: Redis,
    event_type: CustomerWebhookEventType,
    customer: Customer,
) -> None:
    if event_type == WebhookEventType.customer_state_changed:
        data = await get_state(session, redis, customer, cache=False)
        await webhook_service.send(
            session,
            customer.workspace,
            WebhookEventType.customer_state_changed,
            data,
        )
    else:
        await webhook_service.send(session, customer.workspace, event_type, customer)

    # For created, updated and deleted events, also trigger a state changed event
    if event_type in (
        WebhookEventType.customer_created,
        WebhookEventType.customer_updated,
        WebhookEventType.customer_deleted,
    ):
        await webhook(session, redis, WebhookEventType.customer_state_changed, customer)


# ── Relations ──


async def load_members(
    session: AsyncReadSession,
    customer_id: uuid.UUID,
) -> Sequence[MemberSchema]:
    members = await member_service.list_by_customer(session, customer_id)
    return [MemberSchema.model_validate(member) for member in members]


async def batch_load_members(
    session: AsyncReadSession,
    customer_ids: Sequence[uuid.UUID],
) -> dict[uuid.UUID, list[MemberSchema]]:
    """Batch-load members for multiple customers (avoids N+1)."""
    if not customer_ids:
        return {}
    all_members = await member_service.list_by_customers(session, customer_ids)
    result: dict[uuid.UUID, list[MemberSchema]] = {}
    for member in all_members:
        schema = MemberSchema.model_validate(member)
        result.setdefault(member.customer_id, []).append(schema)
    return result
