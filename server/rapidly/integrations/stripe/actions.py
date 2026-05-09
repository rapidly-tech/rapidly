"""Stripe API client wrapper: accounts, payments, and identity verification."""

from typing import TYPE_CHECKING, Any, Unpack

import stripe as stripe_lib
import structlog

from rapidly.config import settings
from rapidly.logfire import instrument_httpx
from rapidly.logging import Logger

if TYPE_CHECKING:
    from stripe.params._account_create_params import AccountCreateParams
    from stripe.params._customer_create_params import CustomerCreateParams
    from stripe.params._customer_modify_params import CustomerModifyParams
    from stripe.params._payment_intent_create_params import PaymentIntentCreateParams
    from stripe.params._setup_intent_create_params import SetupIntentCreateParams

    from rapidly.billing.account.types import AccountCreateForWorkspace
    from rapidly.models import User

# ── Module-level Stripe configuration ─────────────────────────────────

_STRIPE_API_VERSION: str = "2026-01-28.clover"

stripe_lib.api_key = settings.STRIPE_SECRET_KEY
stripe_lib.api_version = _STRIPE_API_VERSION

_stripe_http = stripe_lib.HTTPXClient(allow_sync_methods=True)
instrument_httpx(_stripe_http._client_async)
stripe_lib.default_http_client = _stripe_http

_log: Logger = structlog.get_logger(__name__)


# ── Accounts ──


async def create_account(
    account: "AccountCreateForWorkspace", name: str | None
) -> stripe_lib.Account:
    _log.info(
        "stripe.account.create",
        country=account.country,
        name=name,
    )
    create_params: AccountCreateParams = {
        "country": account.country,
        "type": "express",
        "capabilities": {
            "card_payments": {"requested": True},
            "transfers": {"requested": True},
        },
        "settings": {
            "payouts": {"schedule": {"interval": "daily"}},
        },
    }

    if name:
        create_params["business_profile"] = {"name": name}

    return await stripe_lib.Account.create_async(**create_params)


async def update_account(id: str, name: str | None) -> None:
    _log.info(
        "stripe.account.update",
        account_id=id,
        name=name,
    )
    obj = {}
    if name:
        obj["business_profile"] = {"name": name}
    await stripe_lib.Account.modify_async(id, **obj)


async def account_exists(id: str) -> bool:
    try:
        account = await stripe_lib.Account.retrieve_async(id)
        return bool(account)
    except stripe_lib.PermissionError:
        return False


async def delete_account(id: str) -> stripe_lib.Account:
    _log.info(
        "stripe.account.delete",
        account_id=id,
    )
    return await stripe_lib.Account.delete_async(id)


async def create_account_link(
    stripe_id: str, return_path: str
) -> stripe_lib.AccountLink:
    from urllib.parse import quote

    refresh_url = settings.generate_external_url(
        f"/api/integrations/stripe/refresh?return_path={quote(return_path, safe='')}"
    )
    return_url = return_path
    return await stripe_lib.AccountLink.create_async(
        account=stripe_id,
        refresh_url=refresh_url,
        return_url=return_url,
        type="account_onboarding",
    )


async def create_login_link(stripe_id: str) -> stripe_lib.LoginLink:
    return await stripe_lib.Account.create_login_link_async(stripe_id)


# ── Customers ──


async def update_customer(
    id: str,
    **params: Unpack[CustomerModifyParams],
) -> stripe_lib.Customer:
    _log.info(
        "stripe.customer.update",
        customer_id=id,
        email=params.get("email"),
        name=params.get("name"),
    )
    return await stripe_lib.Customer.modify_async(id, **params)


# ── Payment Method Domains ──


async def create_payment_method_domain(
    domain_name: str,
) -> stripe_lib.PaymentMethodDomain:
    _log.info("stripe.payment_method_domain.create", domain_name=domain_name)
    return await stripe_lib.PaymentMethodDomain.create_async(
        domain_name=domain_name, enabled=True
    )


# ── Identity Verification ──


async def get_verification_session(id: str) -> stripe_lib.identity.VerificationSession:
    return await stripe_lib.identity.VerificationSession.retrieve_async(id)


async def create_verification_session(
    user: "User",
) -> stripe_lib.identity.VerificationSession:
    return await stripe_lib.identity.VerificationSession.create_async(
        type="document",
        options={
            "document": {
                "allowed_types": ["driving_license", "id_card", "passport"],
                "require_live_capture": True,
                "require_matching_selfie": True,
            }
        },
        provided_details={
            "email": user.email,
        },
        client_reference_id=str(user.id),
        metadata={"user_id": str(user.id)},
    )


async def redact_verification_session(
    id: str,
) -> stripe_lib.identity.VerificationSession:
    _log.info("stripe.identity.verification_session.redact", id=id)
    return await stripe_lib.identity.VerificationSession.redact_async(id)


# ── Checkout ──


async def create_checkout_session_direct(
    *,
    connected_account_id: str,
    price_cents: int,
    currency: str,
    application_fee_amount: int,
    product_name: str,
    success_url: str,
    cancel_url: str,
    metadata: dict[str, str] | None = None,
    idempotency_key: str | None = None,
) -> stripe_lib.checkout.Session:
    """Create Stripe Checkout Session as Direct Charge on connected account."""
    _log.info(
        "stripe.checkout.session.create_direct",
        connected_account_id=connected_account_id,
        price_cents=price_cents,
        currency=currency,
        application_fee_amount=application_fee_amount,
    )
    params: dict[str, object] = {
        "mode": "payment",
        "line_items": [
            {
                "price_data": {
                    "currency": currency,
                    "unit_amount": price_cents,
                    "product_data": {"name": product_name},
                },
                "quantity": 1,
            }
        ],
        "payment_intent_data": {
            "application_fee_amount": application_fee_amount,
        },
        "success_url": success_url,
        "cancel_url": cancel_url,
        "metadata": metadata or {},
        "stripe_account": connected_account_id,
    }
    if idempotency_key is not None:
        params["idempotency_key"] = idempotency_key
    try:
        return await stripe_lib.checkout.Session.create_async(
            **params,  # type: ignore[arg-type]
        )
    except stripe_lib.StripeError as e:
        _log.error(
            "stripe.checkout.session.create_direct.failed",
            connected_account_id=connected_account_id,
            error=str(e),
        )
        raise


# ── Platform Customers ──


async def create_customer(
    *,
    email: str,
    name: str | None = None,
    metadata: dict[str, str] | None = None,
) -> stripe_lib.Customer:
    """Create a Stripe Customer on the **platform** account for card storage."""
    _log.info("stripe.customer.create", email=email, name=name)
    params: CustomerCreateParams = {"email": email}
    if name:
        params["name"] = name
    if metadata:
        params["metadata"] = metadata
    return await stripe_lib.Customer.create_async(**params)


# ── SetupIntents (card saving without charging) ──


async def create_setup_intent(
    **params: Unpack[SetupIntentCreateParams],
) -> stripe_lib.SetupIntent:
    """Create a SetupIntent on the platform to save a payment method."""
    _log.info(
        "stripe.setup_intent.create",
        customer=params.get("customer"),
    )
    return await stripe_lib.SetupIntent.create_async(**params)


async def get_setup_intent(
    id: str,
    *,
    expand: list[str] | None = None,
) -> stripe_lib.SetupIntent:
    """Retrieve a SetupIntent (e.g. after 3D Secure confirmation)."""
    kwargs: dict[str, Any] = {}
    if expand:
        kwargs["expand"] = expand
    return await stripe_lib.SetupIntent.retrieve_async(id, **kwargs)


# ── PaymentIntents (Destination Charges) ──


async def create_payment_intent_destination(
    *,
    amount: int,
    currency: str,
    customer: str,
    payment_method: str,
    connected_account_id: str,
    application_fee_amount: int,
    metadata: dict[str, str] | None = None,
    off_session: bool = False,
    statement_descriptor_suffix: str | None = None,
    idempotency_key: str | None = None,
) -> stripe_lib.PaymentIntent:
    """Create a Destination Charge PaymentIntent with a saved payment method.

    The charge is created on the platform account with funds transferred
    to the connected account.  ``on_behalf_of`` makes the connected
    account the business of record.
    """
    _log.info(
        "stripe.payment_intent.create_destination",
        amount=amount,
        currency=currency,
        customer=customer,
        connected_account_id=connected_account_id,
        application_fee_amount=application_fee_amount,
    )
    params: PaymentIntentCreateParams = {
        "amount": amount,
        "currency": currency,
        "customer": customer,
        "payment_method": payment_method,
        "confirm": True,
        "off_session": off_session,
        "automatic_payment_methods": {"enabled": True, "allow_redirects": "never"},
        "transfer_data": {"destination": connected_account_id},
        "on_behalf_of": connected_account_id,
        "application_fee_amount": application_fee_amount,
        "metadata": metadata or {},
    }
    if statement_descriptor_suffix:
        params["statement_descriptor_suffix"] = statement_descriptor_suffix
    kwargs: dict[str, Any] = {}
    if idempotency_key:
        kwargs["idempotency_key"] = idempotency_key
    return await stripe_lib.PaymentIntent.create_async(**params, **kwargs)


async def create_checkout_session_destination(
    *,
    connected_account_id: str,
    price_cents: int,
    currency: str,
    application_fee_amount: int,
    product_name: str,
    success_url: str,
    cancel_url: str,
    metadata: dict[str, str] | None = None,
    idempotency_key: str | None = None,
    customer: str | None = None,
    setup_future_usage: str | None = None,
) -> stripe_lib.checkout.Session:
    """Create a Stripe Checkout Session using Destination Charges.

    Unlike ``create_checkout_session_direct``, the charge is created on
    the platform account with ``transfer_data.destination`` routing funds
    to the connected account.  This allows payment methods to be saved on
    the platform customer for cross-workspace reuse.
    """
    _log.info(
        "stripe.checkout.session.create_destination",
        connected_account_id=connected_account_id,
        price_cents=price_cents,
        currency=currency,
        application_fee_amount=application_fee_amount,
        customer=customer,
    )
    params: dict[str, object] = {
        "mode": "payment",
        "line_items": [
            {
                "price_data": {
                    "currency": currency,
                    "unit_amount": price_cents,
                    "product_data": {"name": product_name},
                },
                "quantity": 1,
            }
        ],
        "payment_intent_data": {
            "application_fee_amount": application_fee_amount,
            "transfer_data": {"destination": connected_account_id},
            "on_behalf_of": connected_account_id,
        },
        "success_url": success_url,
        "cancel_url": cancel_url,
        "metadata": metadata or {},
    }
    if customer:
        params["customer"] = customer
    if setup_future_usage:
        params["payment_intent_data"]["setup_future_usage"] = setup_future_usage  # type: ignore[index]
    if idempotency_key is not None:
        params["idempotency_key"] = idempotency_key
    try:
        return await stripe_lib.checkout.Session.create_async(
            **params,  # type: ignore[arg-type]
        )
    except stripe_lib.StripeError as e:
        _log.error(
            "stripe.checkout.session.create_destination.failed",
            connected_account_id=connected_account_id,
            error=str(e),
        )
        raise


# ── Payment Methods ──


async def get_payment_method(
    payment_method_id: str,
) -> stripe_lib.PaymentMethod:
    """Retrieve a Stripe PaymentMethod object."""
    return await stripe_lib.PaymentMethod.retrieve_async(payment_method_id)


async def detach_payment_method(
    payment_method_id: str,
) -> stripe_lib.PaymentMethod:
    """Detach a PaymentMethod from its Stripe Customer."""
    _log.info("stripe.payment_method.detach", payment_method_id=payment_method_id)
    return await stripe_lib.PaymentMethod.detach_async(payment_method_id)
