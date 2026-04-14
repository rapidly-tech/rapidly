"""Background jobs for Stripe Connect webhook event processing.

Provides the ``stripe_webhook_handler`` decorator and individual
handler functions for Stripe events (account updates, payment intents,
charges, disputes, refunds, payouts, identity verification).  Each
handler is dispatched asynchronously via Dramatiq and retried on
transient failures.
"""

import functools
import uuid
from collections.abc import Awaitable, Callable
from typing import Any, cast

import stripe as stripe_lib
import structlog
from dramatiq import Retry

from rapidly.analytics.external_event import actions as external_event_service
from rapidly.billing.account import actions as account_service
from rapidly.billing.payment_method import actions as pm_actions
from rapidly.billing.stripe_connect.capabilities import (
    invalidate_supported_currencies,
)
from rapidly.logging import Logger
from rapidly.platform.user import actions as user_service
from rapidly.worker import (
    AsyncSessionMaker,
    RedisMiddleware,
    TaskPriority,
    actor,
    get_retries,
)

_log: Logger = structlog.get_logger()


# ── Retry helpers ──


def stripe_api_connection_error_retry[**Params, ReturnValue](
    func: Callable[Params, Awaitable[ReturnValue]],
) -> Callable[Params, Awaitable[ReturnValue]]:
    @functools.wraps(func)
    async def wrapper(*args: Params.args, **kwargs: Params.kwargs) -> ReturnValue:
        try:
            return await func(*args, **kwargs)
        except stripe_lib.APIConnectionError as e:
            _log.warning(
                "Retry after Stripe API connection error",
                e=str(e),
                job_try=get_retries(),
            )
            raise Retry() from e

    return wrapper


# ── Account sync ──


@actor(actor_name="stripe.webhook.account.updated", priority=TaskPriority.HIGH)
@stripe_api_connection_error_retry
async def account_updated(event_id: uuid.UUID) -> None:
    async with AsyncSessionMaker() as session:
        async with external_event_service.handle_stripe(session, event_id) as event:
            stripe_account = cast(stripe_lib.Account, event.stripe_data.data.object)
            _log.info(f"Processing Stripe Account {stripe_account.id}")
            account = await account_service.update_account_from_stripe(
                session, stripe_account=stripe_account
            )
            await invalidate_supported_currencies(RedisMiddleware.get(), account.id)


# ── Payment sync ──


async def _create_payment_from_charge(
    session: Any,
    checkout_session: Any,
    stripe_account: str | None,
    buyer_email: str,
    workspace: Any,
) -> Any | None:
    """Retrieve the Stripe charge and create or return an existing Payment record.

    Returns the Payment model instance, or None if the charge could not be
    retrieved or no charge exists on the payment intent.
    """
    from rapidly.billing.payment.queries import PaymentRepository
    from rapidly.core.utils import create_uuid
    from rapidly.enums import PaymentProcessor
    from rapidly.models import Payment
    from rapidly.models.payment import PaymentStatus

    payment_intent_id = checkout_session.payment_intent
    if not payment_intent_id or not isinstance(payment_intent_id, str):
        return None

    try:
        payment_intent = await stripe_lib.PaymentIntent.retrieve_async(
            payment_intent_id,
            stripe_account=stripe_account,
            expand=["latest_charge"],
        )
    except Exception:
        _log.warning(
            "Could not retrieve charge for file share payment",
            payment_intent_id=payment_intent_id,
            session_id=checkout_session.id,
            exc_info=True,
        )
        return None

    charge = payment_intent.latest_charge
    if not charge or not isinstance(charge, stripe_lib.Charge):
        return None

    payment_repo = PaymentRepository.from_session(session)
    existing_payment = await payment_repo.get_by_processor_id(
        PaymentProcessor.stripe, charge.id
    )
    if existing_payment is not None:
        return existing_payment

    payment_method_details = charge.payment_method_details
    method = "unknown"
    method_metadata: dict[str, Any] = {}
    if payment_method_details:
        method = payment_method_details.type
        method_metadata = dict(payment_method_details[payment_method_details.type])
    payment_record = Payment(
        id=create_uuid(),
        processor=PaymentProcessor.stripe,
        processor_id=charge.id,
        status=PaymentStatus.from_stripe_charge(charge.status),
        amount=charge.amount,
        currency=charge.currency,
        method=method,
        method_metadata=method_metadata,
        customer_email=buyer_email,
        workspace=workspace,
    )
    return await payment_repo.update(payment_record)


@actor(
    actor_name="stripe.webhook.checkout.session.completed",
    priority=TaskPriority.HIGH,
)
@stripe_api_connection_error_retry
async def checkout_session_completed(event_id: uuid.UUID) -> None:
    """Handle checkout.session.completed for file sharing Direct Charges.

    Creates Customer and Payment records, then stores all payment details
    directly in FileSharePayment.
    """
    async with AsyncSessionMaker() as session:
        async with external_event_service.handle_stripe(session, event_id) as event:
            checkout_session = cast(
                stripe_lib.checkout.Session, event.stripe_data.data.object
            )
            metadata = checkout_session.metadata or {}
            if metadata.get("platform") != "rapidly":
                return

            # Support both new "share_id" and legacy "product_id" metadata keys
            share_id_str = metadata.get("share_id") or metadata.get("product_id", "")
            if not share_id_str:
                _log.info(
                    "stripe.webhook.checkout.session.completed (no share_id)",
                    session_id=checkout_session.id,
                    channel_slug=metadata.get("channel_slug"),
                )
                return

            # --- Idempotency check via FileSharePayment ---
            from rapidly.sharing.file_sharing.pg_repository import (
                FileSharePaymentRepository,
            )

            fsp_repo = FileSharePaymentRepository.from_session(session)
            fs_payment = await fsp_repo.get_by_stripe_checkout_session_id(
                checkout_session.id
            )
            if fs_payment is not None and fs_payment.status == "completed":
                _log.info(
                    "FileSharePayment already completed for this checkout session",
                    session_id=checkout_session.id,
                    fs_payment_id=fs_payment.id,
                )
                return

            # --- Look up the Share ---
            from rapidly.catalog.share.queries import ShareRepository

            share_repo = ShareRepository.from_session(session)
            share = await share_repo.get_by_id(uuid.UUID(share_id_str))
            if share is None:
                _log.error(
                    "Share not found for file share checkout",
                    share_id=share_id_str,
                    session_id=checkout_session.id,
                )
                return

            await session.refresh(share, ["workspace"])
            workspace = share.workspace

            # --- Extract buyer info from checkout session ---
            customer_details = checkout_session.customer_details
            buyer_email = (
                customer_details.email
                if customer_details and customer_details.email
                else None
            )
            buyer_name = (
                customer_details.name
                if customer_details and customer_details.name
                else None
            )
            if buyer_email is None:
                _log.error(
                    "No buyer email in checkout session",
                    session_id=checkout_session.id,
                )
                return

            amount = checkout_session.amount_total or 0
            currency = checkout_session.currency or "usd"

            # --- Get or create Customer ---
            from rapidly.customers.customer import actions as customer_service

            rapidly_customer = await customer_service.get_or_create_by_email(
                session,
                email=buyer_email,
                workspace_id=workspace.id,
                name=buyer_name,
            )

            # --- Create Payment record from Stripe charge ---
            payment_intent_id = checkout_session.payment_intent
            payment_record = await _create_payment_from_charge(
                session,
                checkout_session,
                stripe_account=event.stripe_data.account,
                buyer_email=buyer_email,
                workspace=workspace,
            )

            # --- Update FileSharePayment with all payment details ---
            if fs_payment is not None:
                update_dict: dict[str, Any] = {
                    "buyer_email": buyer_email,
                    "buyer_name": buyer_name,
                    "status": "completed",
                    "amount_cents": amount,
                    "currency": currency,
                    "customer_id": rapidly_customer.id,
                    "stripe_payment_intent_id": payment_intent_id
                    if isinstance(payment_intent_id, str)
                    else None,
                }
                if payment_record is not None:
                    update_dict["payment_id"] = payment_record.id
                await fsp_repo.update(
                    fs_payment,
                    update_dict=update_dict,
                    flush=True,
                )

            _log.info(
                "File share payment completed",
                fs_payment_id=fs_payment.id if fs_payment else None,
                share_id=share.id,
                customer_id=rapidly_customer.id,
                amount=amount,
                currency=currency,
                session_id=checkout_session.id,
                channel_slug=metadata.get("channel_slug"),
            )


# ── SetupIntent (card saving) ──


@actor(
    actor_name="stripe.webhook.setup_intent.succeeded",
    priority=TaskPriority.HIGH,
)
@stripe_api_connection_error_retry
async def setup_intent_succeeded(event_id: uuid.UUID) -> None:
    """Save the payment method when a SetupIntent completes successfully."""
    async with AsyncSessionMaker() as session:
        async with external_event_service.handle_stripe(session, event_id) as event:
            setup_intent = cast(stripe_lib.SetupIntent, event.stripe_data.data.object)
            metadata = setup_intent.metadata or {}

            # Only process our own SetupIntents
            customer_id_str = metadata.get("rapidly_customer_id")
            if not customer_id_str:
                return

            if setup_intent.payment_method is None:
                _log.warning(
                    "SetupIntent succeeded but no payment_method attached",
                    setup_intent_id=setup_intent.id,
                )
                return

            # Find the local customer
            from rapidly.customers.customer.queries import CustomerRepository

            customer_repo = CustomerRepository.from_session(session)
            customer = await customer_repo.get_by_id(uuid.UUID(customer_id_str))
            if customer is None:
                _log.error(
                    "Customer not found for setup_intent",
                    customer_id=customer_id_str,
                    setup_intent_id=setup_intent.id,
                )
                return

            # Retrieve the full PaymentMethod object
            from rapidly.integrations.stripe import actions as stripe_service

            pm_id = (
                setup_intent.payment_method
                if isinstance(setup_intent.payment_method, str)
                else setup_intent.payment_method.id
            )
            stripe_pm = await stripe_service.get_payment_method(pm_id)

            # Upsert the payment method locally
            payment_method = await pm_actions.upsert_from_stripe(
                session, customer, stripe_pm, flush=True
            )

            # If this is the customer's first card, set it as default
            existing = await pm_actions.list_for_customer(session, customer.id)
            if len(existing) == 1:
                await pm_actions.set_default_internal(session, customer, payment_method)

            _log.info(
                "Payment method saved from SetupIntent",
                customer_id=str(customer.id),
                payment_method_id=str(payment_method.id),
                type=payment_method.type,
            )


# ── PaymentIntent (Destination Charges) ──


@actor(
    actor_name="stripe.webhook.payment_intent.succeeded",
    priority=TaskPriority.HIGH,
)
@stripe_api_connection_error_retry
async def payment_intent_succeeded(event_id: uuid.UUID) -> None:
    """Handle a successful Destination Charge PaymentIntent."""
    async with AsyncSessionMaker() as session:
        async with external_event_service.handle_stripe(session, event_id) as event:
            payment_intent = cast(
                stripe_lib.PaymentIntent, event.stripe_data.data.object
            )
            metadata = payment_intent.metadata or {}
            if metadata.get("platform") != "rapidly":
                return

            channel_slug = metadata.get("channel_slug", "")
            share_id = metadata.get("share_id", "")

            if not channel_slug and not share_id:
                _log.info(
                    "payment_intent.succeeded with no channel_slug or share_id",
                    payment_intent_id=payment_intent.id,
                )
                return

            # Find the FileSharePayment by payment_intent_id
            from rapidly.sharing.file_sharing.pg_repository import (
                FileSharePaymentRepository,
            )

            fsp_repo = FileSharePaymentRepository.from_session(session)
            fs_payment = await fsp_repo.get_by_stripe_payment_intent_id(
                payment_intent.id
            )

            # If not found by PI ID, log warning but don't guess
            if fs_payment is None:
                _log.warning(
                    "No FileSharePayment found for payment_intent",
                    payment_intent_id=payment_intent.id,
                    channel_slug=channel_slug,
                )

            if fs_payment is not None and fs_payment.status != "completed":
                update_dict: dict[str, Any] = {
                    "status": "completed",
                    "stripe_payment_intent_id": payment_intent.id,
                }
                await fsp_repo.update(fs_payment, update_dict=update_dict, flush=True)

            _log.info(
                "Destination charge payment_intent succeeded",
                payment_intent_id=payment_intent.id,
                channel_slug=channel_slug,
                fs_payment_id=str(fs_payment.id) if fs_payment else None,
            )


@actor(
    actor_name="stripe.webhook.payment_intent.payment_failed",
    priority=TaskPriority.HIGH,
)
@stripe_api_connection_error_retry
async def payment_intent_payment_failed(event_id: uuid.UUID) -> None:
    """Handle a failed Destination Charge PaymentIntent."""
    async with AsyncSessionMaker() as session:
        async with external_event_service.handle_stripe(session, event_id) as event:
            payment_intent = cast(
                stripe_lib.PaymentIntent, event.stripe_data.data.object
            )
            metadata = payment_intent.metadata or {}
            if metadata.get("platform") != "rapidly":
                return

            # Find and mark the FileSharePayment as failed
            from rapidly.sharing.file_sharing.pg_repository import (
                FileSharePaymentRepository,
            )

            fsp_repo = FileSharePaymentRepository.from_session(session)
            fs_payment = await fsp_repo.get_by_stripe_payment_intent_id(
                payment_intent.id
            )

            if fs_payment is not None and fs_payment.status == "pending":
                await fsp_repo.update(
                    fs_payment,
                    update_dict={"status": "failed"},
                    flush=True,
                )

            _log.info(
                "Destination charge payment_intent failed",
                payment_intent_id=payment_intent.id,
            )


# ── Identity verification ──


@actor(
    actor_name="stripe.webhook.identity.verification_session.verified",
    priority=TaskPriority.HIGH,
)
async def identity_verification_session_verified(event_id: uuid.UUID) -> None:
    async with AsyncSessionMaker() as session:
        async with external_event_service.handle_stripe(session, event_id) as event:
            verification_session = cast(
                stripe_lib.identity.VerificationSession, event.stripe_data.data.object
            )
            await user_service.identity_verification_verified(
                session, verification_session
            )


@actor(
    actor_name="stripe.webhook.identity.verification_session.processing",
    priority=TaskPriority.HIGH,
)
async def identity_verification_session_processing(event_id: uuid.UUID) -> None:
    async with AsyncSessionMaker() as session:
        async with external_event_service.handle_stripe(session, event_id) as event:
            verification_session = cast(
                stripe_lib.identity.VerificationSession, event.stripe_data.data.object
            )
            await user_service.identity_verification_pending(
                session, verification_session
            )


@actor(
    actor_name="stripe.webhook.identity.verification_session.requires_input",
    priority=TaskPriority.HIGH,
)
async def identity_verification_session_requires_input(event_id: uuid.UUID) -> None:
    async with AsyncSessionMaker() as session:
        async with external_event_service.handle_stripe(session, event_id) as event:
            verification_session = cast(
                stripe_lib.identity.VerificationSession, event.stripe_data.data.object
            )
            await user_service.identity_verification_failed(
                session, verification_session
            )


@actor(
    actor_name="stripe.webhook.identity.verification_session.canceled",
    priority=TaskPriority.HIGH,
)
async def identity_verification_session_canceled(event_id: uuid.UUID) -> None:
    async with AsyncSessionMaker() as session:
        async with external_event_service.handle_stripe(session, event_id) as event:
            verification_session = cast(
                stripe_lib.identity.VerificationSession, event.stripe_data.data.object
            )
            await user_service.identity_verification_failed(
                session, verification_session
            )
