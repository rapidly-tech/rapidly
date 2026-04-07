"""Payment method business logic: CRUD, Stripe sync, and platform customer management."""

from __future__ import annotations

from typing import cast
from uuid import UUID

import stripe as stripe_lib

from rapidly.customers.customer.queries import CustomerRepository
from rapidly.enums import PaymentProcessor
from rapidly.errors import RapidlyError
from rapidly.integrations.stripe import actions as stripe_service
from rapidly.models import Customer, PaymentMethod
from rapidly.postgres import AsyncSession

from .queries import PaymentMethodRepository
from .types import (
    PaymentMethodConfirm,
    PaymentMethodCreate,
    PaymentMethodCreateRequiresActionResponse,
    PaymentMethodCreateResponse,
    PaymentMethodCreateSucceededResponse,
    PaymentMethodSchema,
)


class PaymentMethodError(RapidlyError): ...


class CustomerNotReady(PaymentMethodError):
    def __init__(self) -> None:
        super().__init__("Customer does not have a Stripe customer ID.", 400)


# ── Reads ──


async def list_for_customer(
    session: AsyncSession,
    customer_id: UUID,
) -> list[PaymentMethod]:
    repo = PaymentMethodRepository.from_session(session)
    return await repo.list_by_customer(customer_id)


async def get(
    session: AsyncSession,
    payment_method_id: UUID,
) -> PaymentMethod | None:
    repo = PaymentMethodRepository.from_session(session)
    return await repo.get_by_id(payment_method_id)


# ── Platform Stripe Customer Management ──


async def ensure_stripe_customer(
    session: AsyncSession,
    customer: Customer,
) -> Customer:
    """Ensure the customer has a platform-level Stripe Customer ID.

    Creates one if ``customer.stripe_customer_id`` is None and persists it.
    Uses a savepoint to handle concurrent creation races safely.
    """
    if customer.stripe_customer_id is not None:
        return customer

    stripe_customer = await stripe_service.create_customer(
        email=customer.email,
        name=customer.billing_name,
        metadata={
            "rapidly_customer_id": str(customer.id),
            "workspace_id": str(customer.workspace_id),
        },
    )

    customer_repo = CustomerRepository.from_session(session)
    try:
        async with session.begin_nested():
            customer = await customer_repo.update(
                customer, update_dict={"stripe_customer_id": stripe_customer.id}
            )
    except Exception:
        # Concurrent request may have set it first — re-read
        await session.refresh(customer)
        if customer.stripe_customer_id is None:
            raise
    return customer


# ── Writes ──


async def upsert_from_stripe(
    session: AsyncSession,
    customer: Customer,
    stripe_pm: stripe_lib.PaymentMethod,
    *,
    flush: bool = False,
) -> PaymentMethod:
    """Create or update a local PaymentMethod from a Stripe PaymentMethod object."""
    repo = PaymentMethodRepository.from_session(session)

    payment_method = await repo.get_by_customer_and_processor_id(
        customer.id,
        PaymentProcessor.stripe,
        stripe_pm.id,
        include_deleted=True,
    )

    pm_type = stripe_pm.type
    raw_metadata = dict(stripe_pm[pm_type] or {})
    # Whitelist only display-safe fields — avoid storing full Stripe sub-object
    # which may contain fingerprint, IIN, network tokens, etc.
    _SAFE_FIELDS = {"brand", "last4", "exp_month", "exp_year", "funding", "wallet"}
    pm_metadata = {k: v for k, v in raw_metadata.items() if k in _SAFE_FIELDS}

    if payment_method is None:
        payment_method = PaymentMethod(
            processor=PaymentProcessor.stripe,
            processor_id=stripe_pm.id,
            customer_id=customer.id,
            type=pm_type,
            method_metadata=pm_metadata,
        )
        return await repo.create(payment_method, flush=flush)

    payment_method.type = pm_type
    payment_method.method_metadata = pm_metadata
    payment_method.deleted_at = None  # Restore if it was soft-deleted
    return await repo.update(payment_method, flush=flush)


async def add_payment_method(
    session: AsyncSession,
    customer: Customer,
    data: PaymentMethodCreate,
) -> PaymentMethodCreateResponse:
    """Start the add-card flow via Stripe SetupIntent.

    Creates a platform Stripe Customer if needed, then creates a
    confirmed SetupIntent with the provided confirmation token.
    """
    customer = await ensure_stripe_customer(session, customer)
    assert customer.stripe_customer_id is not None

    setup_intent = await stripe_service.create_setup_intent(
        automatic_payment_methods={"enabled": True},
        confirm=True,
        confirmation_token=data.confirmation_token_id,
        customer=customer.stripe_customer_id,
        metadata={
            "rapidly_customer_id": str(customer.id),
            "workspace_id": str(customer.workspace_id),
        },
        return_url=data.return_url,
        expand=["payment_method"],
    )

    return await _save_payment_method(
        session, customer, setup_intent, set_default=data.set_default
    )


async def confirm_payment_method(
    session: AsyncSession,
    customer: Customer,
    data: PaymentMethodConfirm,
) -> PaymentMethodCreateResponse:
    """Complete the add-card flow after 3D Secure verification."""
    if customer.stripe_customer_id is None:
        raise CustomerNotReady()

    setup_intent = await stripe_service.get_setup_intent(
        data.setup_intent_id,
        expand=["payment_method"],
    )

    # Verify this SetupIntent belongs to this customer
    if setup_intent.customer is None:
        raise PaymentMethodError("SetupIntent has no customer.", 400)

    customer_id = (
        setup_intent.customer
        if isinstance(setup_intent.customer, str)
        else setup_intent.customer.id
    )
    if customer_id != customer.stripe_customer_id:
        raise PaymentMethodError("SetupIntent does not belong to this customer.", 400)

    return await _save_payment_method(
        session, customer, setup_intent, set_default=data.set_default
    )


async def set_default(
    session: AsyncSession,
    customer: Customer,
    payment_method_id: UUID,
) -> Customer:
    """Set a payment method as the customer's default."""
    repo = PaymentMethodRepository.from_session(session)
    pm = await repo.get_by_id(payment_method_id)
    if pm is None or pm.customer_id != customer.id:
        raise PaymentMethodError("Payment method not found.", 404)

    customer_repo = CustomerRepository.from_session(session)
    customer = await customer_repo.update(
        customer, update_dict={"default_payment_method_id": payment_method_id}
    )

    # Also update Stripe's default
    if customer.stripe_customer_id:
        await stripe_service.update_customer(
            customer.stripe_customer_id,
            invoice_settings={"default_payment_method": pm.processor_id},
        )

    return customer


async def delete(
    session: AsyncSession,
    payment_method: PaymentMethod,
) -> None:
    """Soft-delete the payment method and detach from Stripe.

    If this was the customer's default payment method, clears the FK.
    """
    # Clear default_payment_method_id if this PM was the default
    customer_repo = CustomerRepository.from_session(session)
    customer = await customer_repo.get_by_id(payment_method.customer_id)
    if customer and customer.default_payment_method_id == payment_method.id:
        await customer_repo.update(
            customer, update_dict={"default_payment_method_id": None}
        )

    if payment_method.processor == PaymentProcessor.stripe:
        try:
            await stripe_service.detach_payment_method(payment_method.processor_id)
        except stripe_lib.InvalidRequestError:
            pass  # Already detached

    repo = PaymentMethodRepository.from_session(session)
    await repo.soft_delete(payment_method)


# ── Internal ──


async def _save_payment_method(
    session: AsyncSession,
    customer: Customer,
    setup_intent: stripe_lib.SetupIntent,
    *,
    set_default: bool,
) -> PaymentMethodCreateResponse:
    """Save the payment method from a completed/requires_action SetupIntent."""
    if setup_intent.status == "requires_action":
        if setup_intent.client_secret is None:
            raise PaymentMethodError(
                "SetupIntent requires action but has no client_secret.", 400
            )
        return PaymentMethodCreateRequiresActionResponse(
            client_secret=setup_intent.client_secret,
        )

    if setup_intent.status != "succeeded":
        raise PaymentMethodError(
            f"SetupIntent has unexpected status: {setup_intent.status}.", 400
        )

    if setup_intent.payment_method is None:
        raise PaymentMethodError(
            "SetupIntent succeeded but has no payment method.", 400
        )

    # SetupIntent succeeded — persist the payment method
    stripe_pm = cast(stripe_lib.PaymentMethod, setup_intent.payment_method)
    payment_method = await upsert_from_stripe(session, customer, stripe_pm, flush=True)

    if set_default:
        await set_default_internal(session, customer, payment_method)

    return PaymentMethodCreateSucceededResponse(
        payment_method=_to_schema(payment_method, customer),
    )


async def set_default_internal(
    session: AsyncSession,
    customer: Customer,
    payment_method: PaymentMethod,
) -> None:
    """Set the payment method as default (internal, skips ownership check)."""
    customer_repo = CustomerRepository.from_session(session)
    await customer_repo.update(
        customer, update_dict={"default_payment_method_id": payment_method.id}
    )

    if customer.stripe_customer_id:
        await stripe_service.update_customer(
            customer.stripe_customer_id,
            invoice_settings={"default_payment_method": payment_method.processor_id},
        )


def _to_schema(
    pm: PaymentMethod,
    customer: Customer,
) -> PaymentMethodSchema:
    """Convert a PaymentMethod model to its API schema."""
    return PaymentMethodSchema(
        id=pm.id,
        created_at=pm.created_at,
        modified_at=pm.modified_at,
        processor=pm.processor,
        type=pm.type,
        brand=pm.brand,
        last4=pm.last4,
        exp_month=pm.exp_month,
        exp_year=pm.exp_year,
        is_default=customer.default_payment_method_id == pm.id,
    )
