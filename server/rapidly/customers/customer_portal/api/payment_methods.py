"""Customer-portal payment method routes: list, add, confirm, delete, set default."""

from fastapi import Depends
from pydantic import UUID4

from rapidly.billing.payment_method import actions as pm_actions
from rapidly.billing.payment_method.types import (
    PaymentMethodConfirm,
    PaymentMethodCreate,
    PaymentMethodCreateResponse,
    PaymentMethodSchema,
)
from rapidly.errors import NotPermitted
from rapidly.openapi import APITag
from rapidly.postgres import AsyncSession, get_db_session
from rapidly.routing import APIRouter

from .. import permissions as auth
from ..utils import get_customer

router = APIRouter(prefix="/payment-methods", tags=["payment_methods", APITag.public])


@router.get(
    "",
    summary="List Payment Methods",
    response_model=list[PaymentMethodSchema],
)
async def list_payment_methods(
    auth_subject: auth.CustomerPortalUnionBillingRead,
    session: AsyncSession = Depends(get_db_session),
) -> list[PaymentMethodSchema]:
    """List all saved payment methods for the authenticated customer."""
    customer = get_customer(auth_subject)
    methods = await pm_actions.list_for_customer(session, customer.id)
    return [
        PaymentMethodSchema(
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
        for pm in methods
    ]


@router.post(
    "",
    summary="Add Payment Method",
    status_code=201,
    response_model=PaymentMethodCreateResponse,
)
async def add_payment_method(
    body: PaymentMethodCreate,
    auth_subject: auth.CustomerPortalUnionBillingWrite,
    session: AsyncSession = Depends(get_db_session),
) -> PaymentMethodCreateResponse:
    """Add a new payment method via Stripe SetupIntent.

    Returns ``succeeded`` with the saved payment method, or
    ``requires_action`` with a ``client_secret`` for 3D Secure.
    """
    customer = get_customer(auth_subject)
    return await pm_actions.add_payment_method(session, customer, body)


@router.post(
    "/confirm",
    summary="Confirm Payment Method",
    status_code=201,
    response_model=PaymentMethodCreateResponse,
)
async def confirm_payment_method(
    body: PaymentMethodConfirm,
    auth_subject: auth.CustomerPortalUnionBillingWrite,
    session: AsyncSession = Depends(get_db_session),
) -> PaymentMethodCreateResponse:
    """Complete the add-card flow after 3D Secure verification."""
    customer = get_customer(auth_subject)
    return await pm_actions.confirm_payment_method(session, customer, body)


@router.delete(
    "/{id}",
    summary="Delete Payment Method",
    status_code=204,
)
async def delete_payment_method(
    id: UUID4,
    auth_subject: auth.CustomerPortalUnionBillingWrite,
    session: AsyncSession = Depends(get_db_session),
) -> None:
    """Remove a saved payment method."""
    customer = get_customer(auth_subject)
    pm = await pm_actions.get(session, id)
    if pm is None or pm.customer_id != customer.id:
        raise NotPermitted("Payment method not found.")
    await pm_actions.delete(session, pm)


@router.post(
    "/{id}/default",
    summary="Set Default Payment Method",
    status_code=200,
    response_model=PaymentMethodSchema,
)
async def set_default_payment_method(
    id: UUID4,
    auth_subject: auth.CustomerPortalUnionBillingWrite,
    session: AsyncSession = Depends(get_db_session),
) -> PaymentMethodSchema:
    """Set a payment method as the customer's default."""
    customer = get_customer(auth_subject)
    customer = await pm_actions.set_default(session, customer, id)
    pm = await pm_actions.get(session, id)
    assert pm is not None
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
        is_default=True,
    )
