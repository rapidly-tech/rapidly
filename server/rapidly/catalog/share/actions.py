"""Share catalogue management: prices, media, custom fields, and archival."""

import uuid
from collections import defaultdict
from collections.abc import Sequence
from typing import Literal

from sqlalchemy.orm import selectinload

from rapidly.catalog.custom_field.actions import custom_field as custom_field_service
from rapidly.catalog.file import actions as file_service
from rapidly.catalog.share.guard import (
    is_static_price,
)
from rapidly.catalog.share.queries import ShareRepository
from rapidly.core.db.postgres import AsyncReadSession, AsyncSession
from rapidly.core.metadata import MetadataQuery
from rapidly.core.ordering import Sorting
from rapidly.core.pagination import PaginationParams
from rapidly.errors import (
    RequestValidationError,
    ValidationError,
)
from rapidly.identity.auth.models import AuthPrincipal
from rapidly.messaging.webhook import actions as webhook_service
from rapidly.models import (
    Share,
    ShareMedia,
    SharePrice,
    ShareVisibility,
    User,
    Workspace,
)
from rapidly.models.share_custom_field import ShareCustomField
from rapidly.models.share_price import SharePriceSource
from rapidly.models.webhook_endpoint import WebhookEventType
from rapidly.platform.workspace.queries import WorkspaceRepository
from rapidly.platform.workspace.resolver import get_payload_workspace

from .ordering import ShareSortProperty
from .types import (
    ExistingSharePrice,
    ShareCreate,
    SharePriceCreate,
    ShareUpdate,
)

# ── Reads ──


async def list_shares(
    session: AsyncReadSession,
    auth_subject: AuthPrincipal[User | Workspace],
    *,
    id: Sequence[uuid.UUID] | None = None,
    workspace_id: Sequence[uuid.UUID] | None = None,
    query: str | None = None,
    is_archived: bool | None = None,
    visibility: Sequence[ShareVisibility] | None = None,
    metadata: MetadataQuery | None = None,
    pagination: PaginationParams,
    sorting: Sequence[Sorting[ShareSortProperty]] = (
        (ShareSortProperty.created_at, True),
    ),
) -> tuple[Sequence[Share], int]:
    repository = ShareRepository.from_session(session)
    statement = repository.get_list_statement(auth_subject)
    statement = repository.apply_list_filters(
        statement,
        id=id,
        workspace_id=workspace_id,
        query=query,
        is_archived=is_archived,
        visibility=visibility,
        metadata=metadata,
    )
    statement = repository.apply_sorting(statement, sorting)

    statement = statement.options(
        selectinload(Share.share_medias),
        selectinload(Share.attached_custom_fields),
    )

    return await repository.paginate(
        statement, limit=pagination.limit, page=pagination.page
    )


async def get(
    session: AsyncReadSession,
    auth_subject: AuthPrincipal[User | Workspace],
    id: uuid.UUID,
) -> Share | None:
    repository = ShareRepository.from_session(session)
    statement = (
        repository.get_readable_statement(auth_subject)
        .where(Share.id == id)
        .options(*repository.get_eager_options())
    )
    return await repository.get_one_or_none(statement)


# ── Writes ──


async def create(
    session: AsyncSession,
    create_schema: ShareCreate,
    auth_subject: AuthPrincipal[User | Workspace],
) -> Share:
    repository = ShareRepository.from_session(session)
    workspace = await get_payload_workspace(session, auth_subject, create_schema)

    errors: list[ValidationError] = []
    prices, _, _, prices_errors = await get_validated_prices(
        session,
        workspace,
        create_schema.prices,
        None,
        auth_subject,
    )
    errors.extend(prices_errors)

    share = await repository.create(
        Share(
            workspace=workspace,
            prices=prices,
            all_prices=prices,
            share_medias=[],
            attached_custom_fields=[],
            **create_schema.model_dump(
                exclude={
                    "workspace_id",
                    "prices",
                    "medias",
                    "attached_custom_fields",
                },
                by_alias=True,
            ),
        ),
        flush=True,
    )
    if share.id is None:
        raise ValueError("share.id must not be None after creation")

    if create_schema.medias is not None:
        for order, file_id in enumerate(create_schema.medias):
            file = await file_service.get_selectable_share_media_file(
                session, file_id, workspace_id=share.workspace_id
            )
            if file is None:
                errors.append(
                    {
                        "type": "value_error",
                        "loc": ("body", "medias", order),
                        "msg": "File does not exist or is not yet uploaded.",
                        "input": file_id,
                    }
                )
                continue
            share.share_medias.append(ShareMedia(file=file, order=order))

    for order, attached_custom_field in enumerate(create_schema.attached_custom_fields):
        custom_field = await custom_field_service.get_by_workspace_and_id(
            session,
            attached_custom_field.custom_field_id,
            workspace.id,
        )
        if custom_field is None:
            errors.append(
                {
                    "type": "value_error",
                    "loc": ("body", "attached_custom_fields", order),
                    "msg": "Custom field does not exist.",
                    "input": attached_custom_field.custom_field_id,
                }
            )
            continue
        share.attached_custom_fields.append(
            ShareCustomField(
                custom_field=custom_field,
                order=order,
                required=attached_custom_field.required,
            )
        )

    if errors:
        raise RequestValidationError(errors)

    await session.flush()

    await _after_share_created(session, auth_subject, share)

    return share


async def update(
    session: AsyncSession,
    share: Share,
    update_schema: ShareUpdate,
    auth_subject: AuthPrincipal[User | Workspace],
) -> Share:
    errors: list[ValidationError] = []

    # Validate prices
    existing_prices = set(share.prices)
    added_prices: list[SharePrice] = []
    if update_schema.prices is not None:
        (
            _,
            existing_prices,
            added_prices,
            prices_errors,
        ) = await get_validated_prices(
            session,
            share.workspace,
            update_schema.prices,
            share,
            auth_subject,
        )
        errors.extend(prices_errors)

    if update_schema.medias is not None:
        medias_errors: list[ValidationError] = []
        nested = await session.begin_nested()
        share.medias = []
        await session.flush()

        for order, file_id in enumerate(update_schema.medias):
            file = await file_service.get_selectable_share_media_file(
                session, file_id, workspace_id=share.workspace_id
            )
            if file is None:
                medias_errors.append(
                    {
                        "type": "value_error",
                        "loc": ("body", "medias", order),
                        "msg": "File does not exist or is not yet uploaded.",
                        "input": file_id,
                    }
                )
                continue
            share.share_medias.append(ShareMedia(file=file, order=order))

        if medias_errors:
            await nested.rollback()
            errors.extend(medias_errors)

    if update_schema.attached_custom_fields is not None:
        attached_custom_fields_errors: list[ValidationError] = []
        nested = await session.begin_nested()
        share.attached_custom_fields = []
        await session.flush()

        for order, attached_custom_field in enumerate(
            update_schema.attached_custom_fields
        ):
            custom_field = await custom_field_service.get_by_workspace_and_id(
                session,
                attached_custom_field.custom_field_id,
                share.workspace_id,
            )
            if custom_field is None:
                attached_custom_fields_errors.append(
                    {
                        "type": "value_error",
                        "loc": ("body", "attached_custom_fields", order),
                        "msg": "Custom field does not exist.",
                        "input": attached_custom_field.custom_field_id,
                    }
                )
                continue
            share.attached_custom_fields.append(
                ShareCustomField(
                    custom_field=custom_field,
                    order=order,
                    required=attached_custom_field.required,
                )
            )

        if attached_custom_fields_errors:
            await nested.rollback()
            errors.extend(attached_custom_fields_errors)

    if errors:
        raise RequestValidationError(errors)

    if share.is_archived and update_schema.is_archived is False:
        share.is_archived = False

    if update_schema.name is not None and update_schema.name != share.name:
        share.name = update_schema.name
    if (
        update_schema.description is not None
        and update_schema.description != share.description
    ):
        share.description = update_schema.description

    deleted_prices = set(share.prices) - existing_prices
    for deleted_price in deleted_prices:
        deleted_price.is_archived = True

    if update_schema.is_archived:
        share.is_archived = True

    for attr, value in update_schema.model_dump(
        exclude_unset=True,
        exclude={
            "prices",
            "medias",
            "attached_custom_fields",
            "name",
            "description",
            "is_archived",
        },
        by_alias=True,
    ).items():
        setattr(share, attr, value)

    repo = ShareRepository.from_session(session)
    await repo.update(share, flush=True)

    await session.refresh(share, {"prices", "all_prices"})

    await _after_share_updated(session, share)

    return share


# ── Prices ──


async def get_validated_prices(
    session: AsyncSession,
    workspace: Workspace,
    prices_schema: Sequence[ExistingSharePrice | SharePriceCreate],
    share: Share | None,
    auth_subject: AuthPrincipal[User | Workspace],
    source: SharePriceSource = SharePriceSource.catalog,
    error_prefix: tuple[str, ...] = ("body", "prices"),
) -> tuple[
    list[SharePrice],
    set[SharePrice],
    list[SharePrice],
    list[ValidationError],
]:
    prices: list[SharePrice] = []
    prices_per_currency: defaultdict[str, list[tuple[SharePrice, int]]] = defaultdict(
        list
    )
    existing_prices: set[SharePrice] = set()
    added_prices: list[SharePrice] = []
    errors: list[ValidationError] = []

    for index, price_schema in enumerate(prices_schema):
        if isinstance(price_schema, ExistingSharePrice):
            if share is None:
                raise ValueError("share must not be None for existing price updates")
            price = share.get_price(price_schema.id)
            if price is None:
                errors.append(
                    {
                        "type": "value_error",
                        "loc": (*error_prefix, index),
                        "msg": "Price does not exist.",
                        "input": price_schema.id,
                    }
                )
                continue
            existing_prices.add(price)
        else:
            model_class = price_schema.get_model_class()
            price = model_class(share=share, source=source, **price_schema.model_dump())
            added_prices.append(price)
        prices.append(price)
        prices_per_currency[price.price_currency].append((price, index))

    if len(prices) < 1:
        errors.append(
            {
                "type": "too_short",
                "loc": error_prefix,
                "msg": "At least one price is required.",
                "input": prices_schema,
            }
        )

    # Track price structure per currency for cross-currency validation
    price_structure_per_currency: dict[str, tuple[int]] = {}

    for currency, currency_prices in prices_per_currency.items():
        # Check that only one static price exists per currency
        static_prices = [p for p, _ in currency_prices if is_static_price(p)]
        if len(static_prices) > 1:
            # Bypass that rule for legacy recurring products
            errors.append(
                {
                    "type": "value_error",
                    "loc": error_prefix,
                    "msg": "Only one static price is allowed.",
                    "input": prices_schema,
                }
            )

        # Record the structure: (static_count,)
        price_structure_per_currency[currency] = (len(static_prices),)

    # Check that all currencies have the same price structure
    unique_structures = set(price_structure_per_currency.values())
    if len(unique_structures) > 1:
        errors.append(
            {
                "type": "value_error",
                "loc": error_prefix,
                "msg": (
                    "All price currencies must define the same set of price types."
                ),
                "input": prices_schema,
            }
        )

    # Check that the default presentment currency is present
    if workspace.default_presentment_currency not in price_structure_per_currency:
        errors.append(
            {
                "type": "value_error",
                "loc": error_prefix,
                "msg": "The workspace's default presentment currency must be present in the prices.",
                "input": prices_schema,
            }
        )

    return prices, existing_prices, added_prices, errors


# ── Webhooks ──


async def _after_share_created(
    session: AsyncSession,
    auth_subject: AuthPrincipal[User | Workspace],
    share: Share,
) -> None:
    await _send_webhook(session, share, WebhookEventType.share_created)


async def _after_share_updated(session: AsyncSession, share: Share) -> None:
    await _send_webhook(session, share, WebhookEventType.share_updated)


async def _send_webhook(
    session: AsyncSession,
    share: Share,
    event_type: Literal[WebhookEventType.share_created, WebhookEventType.share_updated],
) -> None:
    workspace_repository = WorkspaceRepository.from_session(session)
    workspace = await workspace_repository.get_by_id(share.workspace_id)
    if workspace is not None:
        await webhook_service.send(session, workspace, event_type, share)
