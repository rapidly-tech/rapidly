"""File sharing service for channel, ICE, and secret sharing operations."""

import base64
import hashlib
import hmac
import secrets
import time
from collections.abc import Callable, Coroutine
from datetime import timedelta
from functools import wraps
from typing import Any, Concatenate, ParamSpec
from uuid import UUID

import structlog
from sqlalchemy.exc import SQLAlchemyError

from rapidly.config import settings
from rapidly.core.db.postgres import AsyncReadSession, AsyncSession
from rapidly.core.pagination import PaginationParams
from rapidly.core.utils import now_utc
from rapidly.identity.auth.models import AuthPrincipal, Subject, User, Workspace
from rapidly.models.file_share_report import FileShareReport, FileShareReportStatus
from rapidly.models.file_share_session import FileShareSession, FileShareSessionStatus
from rapidly.observability.file_sharing_metrics import (
    FILE_SHARING_PG_WRITE_DURATION_SECONDS,
    FILE_SHARING_PG_WRITE_TOTAL,
    FILE_SHARING_SESSION_TOTAL,
)
from rapidly.redis import Redis
from rapidly.worker import dispatch_task

from .pg_repository import (
    FileShareDownloadRepository,
    FileSharePaymentRepository,
    FileShareReportRepository,
    FileShareSessionRepository,
)
from .queries import ChannelRepository, SecretRepository
from .types import (
    ChannelCheckoutResponse,
    ChannelCreateResponse,
    ChannelDestroyResponse,
    ChannelFetchResponse,
    ChannelRenewResponse,
    ChecksumFetchResponse,
    ChecksumUploadResponse,
    DirectPaymentResponse,
    DownloadCompleteResponse,
    ICEConfigResponse,
    ICEServer,
    PasswordAttemptResponse,
    ReaderTokenResponse,
    ReportResponse,
    SecretCheckoutResponse,
    SecretCreateResponse,
    SecretFetchResponse,
    SecretMetadataResponse,
)

_log = structlog.get_logger(__name__)

_P = ParamSpec("_P")


def _pg_dual_write(
    operation: str,
) -> Callable[
    [Callable[Concatenate[AsyncSession, _P], Coroutine[Any, Any, None]]],
    Callable[Concatenate[AsyncSession, _P], Coroutine[Any, Any, None]],
]:
    """Decorator for PG dual-write helpers: measures duration, counts success/error."""

    def decorator(
        fn: Callable[Concatenate[AsyncSession, _P], Coroutine[Any, Any, None]],
    ) -> Callable[Concatenate[AsyncSession, _P], Coroutine[Any, Any, None]]:
        @wraps(fn)
        async def wrapper(
            session: AsyncSession, *args: _P.args, **kwargs: _P.kwargs
        ) -> None:
            start = time.monotonic()
            try:
                await fn(session, *args, **kwargs)
                FILE_SHARING_PG_WRITE_TOTAL.labels(
                    operation=operation, status="success"
                ).inc()
            except SQLAlchemyError:
                FILE_SHARING_PG_WRITE_TOTAL.labels(
                    operation=operation, status="error"
                ).inc()
                _log.exception(
                    "PG dual-write failed",
                    operation=operation,
                )
                # Re-raise for operations that create records — losing these
                # silently would cause the PG audit trail to diverge from Redis.
                if operation in (
                    "create_payment",
                    "create_session",
                    "record_download",
                    "create_report",
                ):
                    raise
            finally:
                FILE_SHARING_PG_WRITE_DURATION_SECONDS.labels(
                    operation=operation
                ).observe(time.monotonic() - start)

        return wrapper

    return decorator


# ── PG Dual-Write Helpers ──


@_pg_dual_write("create_session")
async def _pg_create_session(
    session: AsyncSession,
    *,
    short_slug: str,
    long_slug: str,
    max_downloads: int,
    ttl: int | None,
    price_cents: int | None,
    currency: str,
    title: str | None,
    file_name: str | None,
    file_size_bytes: int | None,
    user_id: str | None,
    workspace_id: str | None,
    share_id: str | None,
    creator_ip_hash: str | None = None,
) -> None:
    """Create a FileShareSession PG record."""

    now = now_utc()
    expires_at = now + timedelta(seconds=ttl) if ttl else None

    repo = FileShareSessionRepository.from_session(session)
    fs_session = FileShareSession(
        short_slug=short_slug,
        long_slug=long_slug,
        status=FileShareSessionStatus.created,
        max_downloads=max_downloads,
        download_count=0,
        price_cents=price_cents,
        currency=currency,
        title=title,
        file_name=file_name,
        file_size_bytes=file_size_bytes,
        ttl_seconds=ttl,
        expires_at=expires_at,
        creator_ip_hash=creator_ip_hash,
        user_id=UUID(user_id) if user_id else None,
        workspace_id=UUID(workspace_id) if workspace_id else None,
        share_id=UUID(share_id) if share_id else None,
    )
    await repo.create(fs_session, flush=True)

    if workspace_id:
        dispatch_task(
            "file_sharing.session_created",
            file_share_session_id=fs_session.id,
        )

    FILE_SHARING_SESSION_TOTAL.labels(status="created").inc()
    _log.info(
        "PG: Created file share session",
        short_slug=short_slug,
        pg_session_id=str(fs_session.id),
    )


@_pg_dual_write("record_download")
async def _pg_record_download(
    session: AsyncSession,
    *,
    slug: str,
    slot_number: int,
    downloader_ip_hash: str | None = None,
) -> None:
    """Create a FileShareDownload PG record and update session lifecycle."""
    from rapidly.models.file_share_download import FileShareDownload

    session_repo = FileShareSessionRepository.from_session(session)
    fs_session = await session_repo.get_by_slug(slug)
    if fs_session is None:
        _log.warning(
            "PG: Session not found for download record",
            slug=slug,
        )
        return

    download_repo = FileShareDownloadRepository.from_session(session)
    download = FileShareDownload(
        session_id=fs_session.id,
        downloader_ip_hash=downloader_ip_hash,
        slot_number=slot_number,
    )
    await download_repo.create(download, flush=True)

    # Atomic increment to avoid lost updates from concurrent downloads
    await session_repo.increment_download_count(fs_session.id)

    # Refresh from DB to get the actual post-increment count
    await session.refresh(fs_session)
    now = now_utc()

    # Activate session on first download (optimistic: only if still "created")
    if fs_session.status == FileShareSessionStatus.created:
        await session_repo.update(
            fs_session,
            update_dict={
                "status": FileShareSessionStatus.active,
                "activated_at": now,
            },
            flush=True,
        )
        FILE_SHARING_SESSION_TOTAL.labels(status="active").inc()

    # Complete session when download limit is reached
    if (
        fs_session.max_downloads > 0
        and fs_session.download_count >= fs_session.max_downloads
    ):
        await session_repo.update(
            fs_session,
            update_dict={
                "status": FileShareSessionStatus.completed,
                "completed_at": now,
            },
            flush=True,
        )
        FILE_SHARING_SESSION_TOTAL.labels(status="completed").inc()

    dispatch_task(
        "file_sharing.download_completed",
        file_share_session_id=fs_session.id,
    )


@_pg_dual_write("update_status")
async def _pg_update_session_status(
    session: AsyncSession,
    *,
    slug: str,
    status: str,
) -> None:
    """Update a FileShareSession status."""

    repo = FileShareSessionRepository.from_session(session)
    fs_session = await repo.get_by_slug(slug)
    if fs_session is None:
        return

    update_dict: dict[str, Any] = {"status": FileShareSessionStatus(status)}
    if status in ("destroyed", "completed"):
        update_dict["completed_at"] = now_utc()
    await repo.update(fs_session, update_dict=update_dict, flush=True)
    FILE_SHARING_SESSION_TOTAL.labels(status=status).inc()


@_pg_dual_write("create_report")
async def _pg_create_report(
    session: AsyncSession,
    *,
    slug: str,
    reporter_ip_hash: str | None = None,
) -> None:
    """Create a FileShareReport PG record."""

    session_repo = FileShareSessionRepository.from_session(session)
    fs_session = await session_repo.get_by_slug(slug)
    if fs_session is None:
        return

    report_repo = FileShareReportRepository.from_session(session)
    report = FileShareReport(
        session_id=fs_session.id,
        reporter_ip_hash=reporter_ip_hash,
    )
    await report_repo.create(report, flush=True)

    await session_repo.update(
        fs_session,
        update_dict={"status": FileShareSessionStatus.reported},
        flush=True,
    )
    FILE_SHARING_SESSION_TOTAL.labels(status="reported").inc()


@_pg_dual_write("create_payment")
async def _pg_create_payment(
    session: AsyncSession,
    *,
    slug: str,
    amount_cents: int,
    currency: str,
    platform_fee_cents: int,
    stripe_checkout_session_id: str | None = None,
    stripe_payment_intent_id: str | None = None,
    payment_method_id: UUID | None = None,
    buyer_ip_hash: str | None = None,
) -> None:
    """Create a FileSharePayment PG record."""
    from rapidly.models.file_share_payment import FileSharePayment

    session_repo = FileShareSessionRepository.from_session(session)
    fs_session = await session_repo.get_by_short_slug(slug)
    if fs_session is None:
        return

    payment_repo = FileSharePaymentRepository.from_session(session)
    payment = FileSharePayment(
        session_id=fs_session.id,
        amount_cents=amount_cents,
        currency=currency,
        platform_fee_cents=platform_fee_cents,
        stripe_checkout_session_id=stripe_checkout_session_id,
        stripe_payment_intent_id=stripe_payment_intent_id,
        payment_method_id=payment_method_id,
    )
    await payment_repo.create(payment, flush=True)


@_pg_dual_write("update_expires")
async def _pg_update_session_expires_at(
    session: AsyncSession,
    *,
    slug: str,
    ttl: int | None,
) -> None:
    """Update expires_at on a FileShareSession."""

    repo = FileShareSessionRepository.from_session(session)
    fs_session = await repo.get_by_slug(slug)
    if fs_session is None:
        return

    now = now_utc()
    expires_at = now + timedelta(seconds=ttl) if ttl else None
    await repo.update(fs_session, update_dict={"expires_at": expires_at}, flush=True)


# ── Secret Sharing ──


async def create_secret_or_file(
    redis: Redis,
    kind: str,
    message: str,
    expiration: int,
    workspace_id: UUID | None = None,
    *,
    price_cents: int | None = None,
    currency: str = "usd",
    title: str | None = None,
    auth_subject: AuthPrincipal[Subject] | None = None,
    read_session: AsyncReadSession | None = None,
) -> SecretCreateResponse:
    """Create a new text secret or file secret.

    For paid secrets (price_cents > 0), verifies the caller is authenticated
    and a member of the specified workspace, then looks up the Stripe account.
    """
    from rapidly.identity.auth.models import is_user_principal

    seller_stripe_id: str | None = None
    ws_id_str: str | None = str(workspace_id) if workspace_id else None

    if price_cents is not None and price_cents > 0:
        if auth_subject is None or not is_user_principal(auth_subject):
            raise ChannelCreationError(
                "Authentication required for paid secrets", status_code=401
            )
        if not workspace_id:
            raise ChannelCreationError("workspace_id is required for paid secrets")
        if read_session is None:
            raise ChannelCreationError("Internal error: read_session required")

        # Verify workspace membership
        from rapidly.platform.workspace.queries import WorkspaceRepository

        workspace_repo = WorkspaceRepository.from_session(read_session)
        statement = workspace_repo.get_readable_statement(auth_subject).where(
            WorkspaceRepository.model.id == workspace_id
        )
        workspace = await workspace_repo.get_one_or_none(statement)
        if workspace is None:
            raise ChannelCreationError(
                "Not a member of this workspace", status_code=403
            )

        # Look up Stripe account
        from rapidly.billing.account.queries import AccountRepository

        account_repo = AccountRepository.from_session(read_session)
        account = await account_repo.get_by_workspace(workspace_id)
        if account is None or not account.stripe_id or not account.is_charges_enabled:
            raise ChannelCreationError(
                "Your Stripe account setup is incomplete. Please finish onboarding in your account settings to accept payments."
            )
        seller_stripe_id = account.stripe_id

    repository = SecretRepository(redis)
    create_fn = repository.create_secret if kind == "secret" else repository.create_file
    item_id = await create_fn(
        message,
        expiration,
        ws_id_str,
        price_cents=price_cents,
        currency=currency,
        title=title,
        seller_stripe_id=seller_stripe_id,
    )
    return SecretCreateResponse(message=item_id)


async def peek_secret_metadata(
    redis: Redis,
    secret_id: str,
) -> SecretMetadataResponse | None:
    """Read secret metadata (title, payment info) without consuming it."""
    repository = SecretRepository(redis)
    peeked = await repository.peek_secret(secret_id)
    if peeked is None:
        return None
    return SecretMetadataResponse(
        title=peeked.title,
        payment_required=peeked.is_paid,
        price_cents=peeked.price_cents,
        currency=peeked.currency,
    )


async def fetch_secret_or_file(
    redis: Redis,
    kind: str,
    item_id: str,
    *,
    payment_token: str | None = None,
    buyer_fingerprint: str = "",
) -> SecretFetchResponse | None:
    """Fetch a text/file secret (deletes after retrieval).

    For paid secrets, checks the payment token. If unpaid, returns
    metadata only. Once payment is verified, the content is returned
    and the secret is consumed.
    """
    repository = SecretRepository(redis)
    peek_fn = repository.peek_secret if kind == "secret" else repository.peek_file
    fetch_fn = repository.fetch_secret if kind == "secret" else repository.fetch_file

    peeked = await peek_fn(item_id)
    if peeked is None:
        return None

    if peeked.is_paid:
        # Check payment token
        payment_verified = False
        if payment_token:
            payment_verified = await repository.validate_secret_payment_token(
                item_id, payment_token, buyer_fingerprint=buyer_fingerprint
            )
        if not payment_verified:
            return SecretFetchResponse(
                message="",
                payment_required=True,
                price_cents=peeked.price_cents,
                currency=peeked.currency,
                title=peeked.title,
            )

    # Free secret or payment verified — consume it
    secret = await fetch_fn(item_id)
    if secret is None:
        return None
    return SecretFetchResponse(message=secret.message)


# ── Secret Checkout ──


async def create_secret_checkout(
    redis: Redis,
    secret_id: str,
    *,
    kind: str = "secret",
    buyer_fingerprint: str = "",
) -> SecretCheckoutResponse | None:
    """Create a Stripe Checkout Session for a paid secret or file.

    Returns None if item not found or not paid.
    Raises ValueError if the seller's Stripe account is not configured.
    """
    from rapidly.integrations.stripe import actions as stripe_service

    from .types import SecretCheckoutResponse

    repository = SecretRepository(redis)
    peek_fn = repository.peek_secret if kind == "secret" else repository.peek_file
    secret = await peek_fn(secret_id)
    if secret is None:
        return None

    if not secret.is_paid or not secret.seller_stripe_id:
        raise ValueError("Item is not configured for payments")

    price_cents = secret.price_cents
    if price_cents is None:
        raise ValueError("price_cents must be set for paid items")

    fee_amount = (price_cents * settings.FILE_SHARING_PLATFORM_FEE_PERCENT) // 10000

    # Generate payment token
    payment_token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(payment_token.encode()).hexdigest()

    # Check TTL of the secret
    ttl = await redis.ttl(repository._key(kind, secret_id))
    if ttl <= 0:
        return None
    await repository.store_secret_payment_token(
        secret_id, token_hash, ttl, buyer_fingerprint=buyer_fingerprint
    )

    product_name = secret.title or (
        "Encrypted Secret" if kind == "secret" else "Encrypted File"
    )
    success_url = settings.generate_frontend_url(
        f"/secret-checkout-return/{secret_id}?session_id={{CHECKOUT_SESSION_ID}}"
    )
    cancel_url = settings.generate_frontend_url(
        f"/secret-checkout-return/{secret_id}?cancelled=true"
    )

    stripe_session = await stripe_service.create_checkout_session_direct(
        connected_account_id=secret.seller_stripe_id,
        price_cents=price_cents,
        currency=secret.currency,
        application_fee_amount=fee_amount,
        product_name=product_name,
        success_url=success_url,
        cancel_url=cancel_url,
        metadata={
            "platform": "rapidly",
            "secret_id": secret_id,
            "kind": kind,
            "workspace_id": secret.workspace_id or "",
        },
        idempotency_key=f"secret-checkout-{secret_id}-{buyer_fingerprint}",
    )

    # Store checkout_session_id → payment_token mapping (bound to secret_id)
    await repository.store_secret_checkout_payment_token(
        secret_id, stripe_session.id, payment_token
    )

    return SecretCheckoutResponse(
        checkout_url=stripe_session.url or "",
        session_id=stripe_session.id,
    )


async def claim_secret_checkout_payment_token(
    redis: Redis,
    secret_id: str,
    checkout_session_id: str,
    *,
    kind: str = "secret",
) -> str | None:
    """Exchange a Stripe checkout session ID for the payment token."""
    repository = SecretRepository(redis)
    peek_fn = repository.peek_secret if kind == "secret" else repository.peek_file
    peeked = await peek_fn(secret_id)
    if peeked is None:
        return None
    return await repository.claim_secret_checkout_payment_token(
        secret_id, checkout_session_id
    )


# ── Channel Creation Validation ──


class ChannelCreationError(Exception):
    """Raised when channel creation validation fails."""

    def __init__(self, detail: str, status_code: int = 400) -> None:
        self.detail = detail
        self.status_code = status_code
        super().__init__(detail)


async def resolve_channel_creation_context(
    read_session: AsyncReadSession,
    auth_subject: AuthPrincipal[Subject],
    *,
    workspace_id_input: UUID | None = None,
    price_cents: int | None = None,
) -> tuple[str | None, str | None, str | None, str | None]:
    """Validate and resolve context for channel creation.

    Returns (user_id, workspace_id, seller_stripe_id, seller_account_id).
    Raises ChannelCreationError on validation failure.
    """
    from rapidly.identity.auth.models import is_user_principal

    seller_stripe_id: str | None = None
    seller_account_id: str | None = None
    user_id: str | None = None
    workspace_id: str | None = None

    if is_user_principal(auth_subject):
        user_id = str(auth_subject.subject.id)
        if workspace_id_input:
            from rapidly.platform.workspace.queries import WorkspaceRepository

            workspace_repo = WorkspaceRepository.from_session(read_session)
            statement = workspace_repo.get_readable_statement(auth_subject).where(
                WorkspaceRepository.model.id == workspace_id_input
            )
            workspace = await workspace_repo.get_one_or_none(statement)
            if workspace is None:
                raise ChannelCreationError(
                    "Not a member of this workspace", status_code=403
                )
            workspace_id = str(workspace_id_input)

    if price_cents is not None and price_cents > 0:
        if not is_user_principal(auth_subject):
            raise ChannelCreationError(
                "Authentication required for paid channels", status_code=401
            )
        if not workspace_id_input:
            raise ChannelCreationError("workspaceId is required for paid channels")
        from rapidly.billing.account.queries import AccountRepository

        account_repo = AccountRepository.from_session(read_session)
        account = await account_repo.get_by_workspace(workspace_id_input)
        if account is None or not account.stripe_id or not account.is_charges_enabled:
            raise ChannelCreationError(
                "Active Stripe account with charges enabled is required for paid channels"
            )
        seller_stripe_id = account.stripe_id
        seller_account_id = str(account.id)

    return user_id, workspace_id, seller_stripe_id, seller_account_id


# ── Channel Lifecycle ──


async def create_channel(
    redis: Redis,
    max_downloads: int = 0,
    ttl: int | None = None,
    *,
    price_cents: int | None = None,
    currency: str = "usd",
    seller_stripe_id: str | None = None,
    seller_account_id: str | None = None,
    user_id: str | None = None,
    title: str | None = None,
    file_name: str | None = None,
    file_size_bytes: int | None = None,
    session: AsyncSession | None = None,
    workspace_id: str | None = None,
    creator_ip_hash: str | None = None,
) -> ChannelCreateResponse:
    """Create a new channel for file sharing."""
    # Resolve default TTL so both Redis and PG use the same value
    if ttl is None:
        if price_cents is not None and price_cents > 0:
            ttl = settings.FILE_SHARING_PAID_CHANNEL_TTL
        else:
            ttl = settings.FILE_SHARING_CHANNEL_TTL

    share_id: str | None = None

    # Create a Share for paid channels
    if (
        price_cents is not None
        and price_cents > 0
        and session is not None
        and workspace_id is not None
    ):
        share_id = await _create_product_for_channel(
            session,
            workspace_id=workspace_id,
            price_cents=price_cents,
            currency=currency,
            file_name=file_name,
        )

    repository = ChannelRepository(redis)
    channel, raw_secret = await repository.create_channel(
        max_downloads,
        ttl,
        price_cents=price_cents,
        currency=currency,
        seller_stripe_id=seller_stripe_id,
        seller_account_id=seller_account_id,
        user_id=user_id,
        title=title,
        file_name=file_name,
        file_size_bytes=file_size_bytes,
        share_id=share_id,
    )

    # PG dual-write
    if session is not None:
        await _pg_create_session(
            session,
            short_slug=channel.short_slug,
            long_slug=channel.long_slug,
            max_downloads=max_downloads,
            ttl=ttl,
            price_cents=price_cents,
            currency=currency,
            title=title,
            file_name=file_name,
            file_size_bytes=file_size_bytes,
            user_id=user_id,
            workspace_id=workspace_id,
            share_id=share_id,
            creator_ip_hash=creator_ip_hash,
        )

    # Invalidate the cached stats so the counter updates immediately
    await redis.delete(_STATS_CACHE_KEY)

    return ChannelCreateResponse(
        secret=raw_secret,
        long_slug=channel.long_slug,
        short_slug=channel.short_slug,
    )


async def _create_product_for_channel(
    session: AsyncSession,
    *,
    workspace_id: str,
    price_cents: int,
    currency: str,
    file_name: str | None,
) -> str | None:
    """Create a Share for a paid file sharing channel."""
    from rapidly.catalog.share.queries import ShareRepository
    from rapidly.models import Share, ShareVisibility
    from rapidly.models.share_price import (
        SharePriceAmountType,
        SharePriceFixed,
        SharePriceSource,
    )
    from rapidly.platform.workspace.queries import WorkspaceRepository

    org_repo = WorkspaceRepository.from_session(session)
    workspace = await org_repo.get_by_id(UUID(workspace_id))
    if workspace is None:
        _log.warning(
            "Workspace not found for share creation",
            workspace_id=workspace_id,
        )
        return None

    product_name = file_name or "File Download"
    price = SharePriceFixed(
        price_amount=price_cents,
        price_currency=currency,
        amount_type=SharePriceAmountType.fixed,
        source=SharePriceSource.catalog,
    )

    share_repo = ShareRepository.from_session(session)
    share = await share_repo.create(
        Share(
            name=product_name,
            description=f"Paid file share - {product_name}",
            workspace=workspace,
            visibility=ShareVisibility.public,
            is_archived=False,
            prices=[price],
            all_prices=[price],
            share_medias=[],
            attached_custom_fields=[],
            user_metadata={"type": "file_share"},
        ),
        flush=True,
    )
    _log.info(
        "Created share for paid file share",
        share_id=str(share.id),
        workspace_id=workspace_id,
    )
    return str(share.id)


async def set_reader_token(
    redis: Redis,
    slug: str,
    secret: str,
    token_hash: str,
) -> ReaderTokenResponse:
    """Register a reader authorization token for a channel."""
    repository = ChannelRepository(redis)
    success = await repository.set_reader_token(slug, secret, token_hash)
    return ReaderTokenResponse(success=success)


async def fetch_channel(
    redis: Redis,
    slug: str,
    reader_token: str | None = None,
    payment_token: str | None = None,
    buyer_fingerprint: str = "",
) -> ChannelFetchResponse | None:
    """Fetch channel info for a downloader.

    If a reader token is registered for the channel, the provided
    reader_token must match (prevents slug enumeration).
    For paid channels, returns pricing info and payment_required flag.
    """
    repository = ChannelRepository(redis)
    channel = await repository.fetch_channel(slug)
    if channel is None:
        return None

    # Block access while reader token registration is pending
    if await repository.is_pending_token(slug, channel=channel):
        return None

    # Validate reader token if one is registered
    if reader_token:
        if not await repository.validate_reader_token(
            slug, reader_token, channel=channel
        ):
            return None
    else:
        # Check if a token is required (one is stored)
        if await repository.has_reader_token(slug, channel=channel):
            # Token required but not provided
            return None

    # Read-only check: are download slots still available?
    # Actual slot claiming happens in record_download_complete to avoid
    # wasting slots on page reloads or failed WebRTC connections.
    if not await repository.check_download_available(slug, channel=channel):
        return None

    # Determine payment status for paid channels
    payment_required = False
    if channel.is_paid:
        if payment_token:
            payment_required = not await repository.validate_payment_token(
                slug,
                payment_token,
                channel=channel,
                buyer_fingerprint=buyer_fingerprint,
            )
        else:
            payment_required = True

    return ChannelFetchResponse(
        available=True,
        title=channel.title,
        price_cents=channel.price_cents,
        currency=channel.currency if channel.is_paid else None,
        file_name=channel.file_name,
        file_size_bytes=channel.file_size_bytes,
        payment_required=payment_required,
    )


async def renew_channel(
    redis: Redis,
    slug: str,
    secret: str,
    ttl: int | None = None,
    *,
    session: AsyncSession | None = None,
) -> ChannelRenewResponse:
    """Renew a channel's TTL.

    Returns ``success=False`` for both "not found" and "invalid secret"
    intentionally — distinguishing them would leak which slugs exist,
    enabling channel enumeration.
    """
    # Resolve default TTL so PG gets the same expiry as Redis
    if ttl is None:
        ttl = settings.FILE_SHARING_CHANNEL_TTL

    repository = ChannelRepository(redis)
    success = await repository.renew_channel(slug, secret, ttl)

    if success and session is not None:
        await _pg_update_session_expires_at(session, slug=slug, ttl=ttl)

    return ChannelRenewResponse(success=success)


async def destroy_channel(
    redis: Redis,
    slug: str,
    secret: str,
    *,
    session: AsyncSession | None = None,
) -> ChannelDestroyResponse:
    """Request authenticated channel destruction.

    Requires the channel ownership secret to prevent unauthorized destruction.
    - First request marks channel for destruction with a 30-second delay
    - Second request (within delay window) confirms immediate destruction
    - Channel owner can cancel pending destruction by renewing the channel
    """
    repository = ChannelRepository(redis)
    success, is_immediate, message = await repository.request_channel_destruction(
        slug, secret
    )

    if success and is_immediate and session is not None:
        await _pg_update_session_status(session, slug=slug, status="destroyed")

    return ChannelDestroyResponse(
        success=success,
        immediate=is_immediate,
        message=message,
    )


# ── Payments ──


async def _validate_channel_price(
    session: AsyncSession | None,
    channel: "Any",
) -> tuple[int, str]:
    """Cross-check channel price against PG and return (price_cents, currency)."""
    price_cents = channel.price_cents
    currency = channel.currency
    if session is not None:
        try:
            session_repo = FileShareSessionRepository.from_session(session)
            pg_session = await session_repo.get_by_short_slug(channel.short_slug)
            if pg_session is not None and pg_session.price_cents is not None:
                if pg_session.price_cents != price_cents:
                    _log.warning(
                        "Price mismatch: Redis=%d PG=%d for slug=%s — using PG price",
                        price_cents,
                        pg_session.price_cents,
                        channel.short_slug,
                    )
                    price_cents = pg_session.price_cents
                if pg_session.currency != currency:
                    _log.warning(
                        "Currency mismatch: Redis=%s PG=%s for slug=%s — using PG currency",
                        currency,
                        pg_session.currency,
                        channel.short_slug,
                    )
                    currency = pg_session.currency
            elif pg_session is None:
                _log.warning(
                    "No PG session found for slug=%s during checkout price validation",
                    channel.short_slug,
                )
        except Exception as exc:
            _log.exception(
                "Failed to cross-check price against PG for slug=%s",
                channel.short_slug,
            )
            raise ValueError(
                "Price verification failed — please try again later"
            ) from exc
    return price_cents, currency


async def create_checkout(
    redis: Redis,
    slug: str,
    *,
    session: AsyncSession | None = None,
    buyer_fingerprint: str = "",
    payment_method_id: UUID | None = None,
    buyer_customer_id: UUID | None = None,
) -> ChannelCheckoutResponse | DirectPaymentResponse | None:
    """Create a Stripe Checkout Session or direct PaymentIntent for a paid channel.

    Uses Destination Charges (platform creates charge, transfers to connected account).
    If ``payment_method_id`` is provided and the buyer has a saved card,
    creates a PaymentIntent directly (no Stripe Checkout redirect).

    ``buyer_customer_id`` must be provided when using ``payment_method_id`` to
    verify the caller owns the payment method (prevents IDOR).
    """
    from rapidly.customers.customer.queries import CustomerRepository
    from rapidly.integrations.stripe import actions as stripe_service

    repository = ChannelRepository(redis)
    channel = await repository.fetch_channel(slug)
    if channel is None:
        return None

    if not channel.is_paid or not channel.seller_stripe_id:
        raise ValueError("Channel is not configured for payments")

    if channel.price_cents is None:
        raise ValueError("Channel price_cents must be set for paid channels")

    price_cents, currency = await _validate_channel_price(session, channel)
    fee_amount = (price_cents * settings.FILE_SHARING_PLATFORM_FEE_PERCENT) // 10000

    # Generate payment token
    payment_token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(payment_token.encode()).hexdigest()

    ttl = await redis.ttl(repository._key(channel.short_slug))
    if ttl <= 0:
        return None
    await repository.store_payment_token(
        channel.short_slug, token_hash, ttl, buyer_fingerprint=buyer_fingerprint
    )

    metadata = {
        "platform": "rapidly",
        "channel_slug": channel.short_slug,
        "user_id": channel.user_id or "",
        "share_id": channel.share_id or "",
    }

    # ── Path B: Saved card → direct PaymentIntent (no redirect) ──
    # Requires buyer_customer_id for ownership verification (prevents IDOR).
    if (
        payment_method_id is not None
        and buyer_customer_id is not None
        and session is not None
    ):
        from rapidly.billing.payment_method import actions as pm_actions

        pm = await pm_actions.get(session, payment_method_id)
        if pm is not None and pm.customer_id == buyer_customer_id:
            # Ownership verified — load customer for Stripe customer ID
            customer_repo = CustomerRepository.from_session(session)
            customer = await customer_repo.get_by_id(pm.customer_id)
            if customer and customer.stripe_customer_id:
                payment_intent = await stripe_service.create_payment_intent_destination(
                    amount=price_cents,
                    currency=currency,
                    customer=customer.stripe_customer_id,
                    payment_method=pm.processor_id,
                    connected_account_id=channel.seller_stripe_id,
                    application_fee_amount=fee_amount,
                    metadata=metadata,
                    off_session=False,
                    idempotency_key=f"pi-{channel.short_slug}-{buyer_fingerprint}",
                )

                # Store checkout mapping for token claim
                await repository.store_checkout_payment_token(
                    channel.short_slug, payment_intent.id, payment_token
                )

                # PG dual-write
                await _pg_create_payment(
                    session,
                    slug=channel.short_slug,
                    amount_cents=price_cents,
                    currency=currency,
                    platform_fee_cents=fee_amount,
                    stripe_checkout_session_id=None,
                    stripe_payment_intent_id=payment_intent.id,
                    payment_method_id=payment_method_id,
                )

                requires_action = payment_intent.status == "requires_action"
                return DirectPaymentResponse(
                    client_secret=payment_intent.client_secret or "",
                    payment_intent_id=payment_intent.id,
                    requires_action=requires_action,
                )

    # ── Path A: No saved card → Stripe Checkout Session (Direct Charges) ──
    product_name = channel.file_name or "File Download"
    success_url = settings.generate_frontend_url(
        f"/checkout-return/{channel.short_slug}?session_id={{CHECKOUT_SESSION_ID}}"
    )
    cancel_url = settings.generate_frontend_url(
        f"/checkout-return/{channel.short_slug}?cancelled=true"
    )

    # Use Direct Charges for Checkout Sessions — compatible with all existing
    # Express accounts. Destination Charges are used only for the saved-card
    # PaymentIntent path (Path B above) where the PM lives on the platform.
    stripe_session = await stripe_service.create_checkout_session_direct(
        connected_account_id=channel.seller_stripe_id,
        price_cents=price_cents,
        currency=currency,
        application_fee_amount=fee_amount,
        product_name=product_name,
        success_url=success_url,
        cancel_url=cancel_url,
        metadata=metadata,
        idempotency_key=f"checkout-{channel.short_slug}-{buyer_fingerprint}",
    )

    # Store checkout_session_id → payment_token mapping
    await repository.store_checkout_payment_token(
        channel.short_slug, stripe_session.id, payment_token
    )

    # PG dual-write
    if session is not None:
        await _pg_create_payment(
            session,
            slug=channel.short_slug,
            amount_cents=price_cents,
            currency=currency,
            platform_fee_cents=fee_amount,
            stripe_checkout_session_id=stripe_session.id,
        )

    return ChannelCheckoutResponse(
        checkout_url=stripe_session.url or "",
        session_id=stripe_session.id,
    )


# ── Downloads ──


async def record_download_complete(
    redis: Redis,
    slug: str,
    reader_token: str,
    *,
    session: AsyncSession | None = None,
    downloader_ip_hash: str | None = None,
) -> DownloadCompleteResponse:
    """Record a completed download and atomically claim a slot.

    This is the primary download-limit enforcement point.
    Slot is claimed here (not on channel fetch) to avoid wasting
    slots on page reloads or failed WebRTC connections.
    """
    repository = ChannelRepository(redis)
    success, remaining, download_count = await repository.record_download_complete(
        slug, reader_token
    )

    if success and session is not None:
        await _pg_record_download(
            session,
            slug=slug,
            slot_number=download_count,
            downloader_ip_hash=downloader_ip_hash,
        )

    return DownloadCompleteResponse(success=success, remaining=remaining)


# ── Reporting ──


async def report_channel(
    redis: Redis,
    slug: str,
    reader_token: str,
    *,
    session: AsyncSession | None = None,
    reporter_ip_hash: str | None = None,
) -> ReportResponse:
    """Report a channel for violation.

    Validates the reporter's reader token, then closes the signaling
    room to prevent new peer connections. Existing P2P connections
    are not affected (they're direct between peers).
    """
    from .signaling import close_room

    repository = ChannelRepository(redis)
    channel = await repository.fetch_channel(slug)
    if channel is None:
        return ReportResponse(success=False)

    # Block during pending-token window (matches fetch_channel behavior)
    if await repository.is_pending_token(slug, channel=channel):
        return ReportResponse(success=False)

    # Always require a valid reader token for reports (prevents anonymous DoS).
    # Reject if no token provided, no token registered, or token doesn't match.
    if not reader_token:
        return ReportResponse(success=False)
    if not await repository.has_reader_token(slug, channel=channel):
        # No reader token registered — cannot authenticate the reporter
        return ReportResponse(success=False)
    if not await repository.validate_reader_token(slug, reader_token, channel=channel):
        return ReportResponse(success=False)

    # Close the signaling room to disconnect peers
    await close_room(channel.short_slug)

    # Delete channel from Redis so the uploader cannot reconnect
    # and the channel is no longer discoverable via fetch_channel.
    await repository.delete_channel(channel)

    _log.info(
        "Channel reported for violation",
        event="channel_reported",
        short_slug=channel.short_slug,
    )

    # PG dual-write
    if session is not None:
        await _pg_create_report(
            session,
            slug=channel.short_slug,
            reporter_ip_hash=reporter_ip_hash,
        )

    return ReportResponse(success=True)


# ── Access Control ──


async def record_password_attempt(
    redis: Redis,
    slug: str,
    secret: str,
) -> PasswordAttemptResponse:
    """Record a password attempt for rate limiting."""
    repository = ChannelRepository(redis)
    allowed = await repository.record_password_attempt(slug, secret)
    return PasswordAttemptResponse(allowed=allowed)


async def claim_checkout_payment_token(
    redis: Redis,
    slug: str,
    checkout_session_id: str,
) -> str | None:
    """Exchange a Stripe checkout session ID for the payment token.

    Verifies the Stripe Checkout Session is actually paid before releasing
    the token.  One-time use — the mapping is deleted atomically on retrieval.
    Returns None if the session_id is invalid, unpaid, or already claimed.
    """
    import stripe as stripe_lib

    repository = ChannelRepository(redis)
    channel = await repository.fetch_channel(slug)
    if channel is None:
        return None

    # Verify payment completed on Stripe before releasing token
    if channel.seller_stripe_id:
        try:
            cs = await stripe_lib.checkout.Session.retrieve_async(
                checkout_session_id,
                stripe_account=channel.seller_stripe_id,
            )
            if cs.payment_status != "paid":
                _log.warning(
                    "Token claim rejected: checkout session not paid",
                    session_id=checkout_session_id,
                    payment_status=cs.payment_status,
                    slug=slug,
                )
                return None
        except stripe_lib.StripeError:
            _log.warning(
                "Could not verify checkout session — allowing claim",
                session_id=checkout_session_id,
                slug=slug,
                exc_info=True,
            )

    return await repository.claim_checkout_payment_token(slug, checkout_session_id)


# ── Checksums ──


async def upload_checksums(
    redis: Redis,
    slug: str,
    secret: str,
    checksums: dict[str, str],
) -> ChecksumUploadResponse:
    """Store SHA-256 checksums for a channel's files."""
    repository = ChannelRepository(redis)
    success = await repository.store_checksums(slug, secret, checksums)
    return ChecksumUploadResponse(success=success)


async def fetch_checksums(
    redis: Redis,
    slug: str,
    reader_token: str,
) -> ChecksumFetchResponse | None:
    """Fetch checksums for a channel."""
    repository = ChannelRepository(redis)
    checksums = await repository.fetch_checksums(slug, reader_token)
    if checksums is None:
        return None
    return ChecksumFetchResponse(checksums=checksums)


# ── ICE / WebRTC ──


async def get_ice_config_for_channel(
    redis: Redis,
    slug: str,
    token: str,
) -> ICEConfigResponse | None:
    """Get ICE config after validating channel and reader token.

    Returns None if the channel is not found. Raises ValueError if
    a reader token is registered but the provided token is invalid.
    """
    repository = ChannelRepository(redis)
    channel = await repository.fetch_channel(slug)
    if channel is None:
        return None
    if not await repository.validate_reader_token(slug, token, channel=channel):
        if await repository.has_reader_token(slug, channel=channel):
            raise ValueError("Invalid reader token")
    return await build_ice_config()


async def build_ice_config() -> ICEConfigResponse:
    """Get ICE server configuration for WebRTC."""
    ice_servers: list[ICEServer] = []

    # Always include STUN
    ice_servers.append(ICEServer(urls=f"stun:{settings.FILE_SHARING_STUN_SERVER}"))

    if settings.FILE_SHARING_COTURN_ENABLED:
        # Generate ephemeral TURN credentials using HMAC-SHA1
        # Protocol: username = "expiry_timestamp:random_label"
        #           credential = Base64(HMAC-SHA1(shared_secret, username))
        # COTURN validates these natively with use-auth-secret — no Redis needed.
        expiry = int(time.time()) + settings.FILE_SHARING_TURN_CREDENTIAL_TTL
        label = secrets.token_hex(8)
        username = f"{expiry}:{label}"
        credential = base64.b64encode(
            hmac.new(
                settings.FILE_SHARING_TURN_SECRET.encode(),
                username.encode(),
                hashlib.sha1,
            ).digest()
        ).decode()

        turn_urls = [
            f"turn:{settings.FILE_SHARING_TURN_HOST}:{settings.FILE_SHARING_TURN_PORT}",
        ]
        # Only include turns: URL when TLS is actually configured — advertising
        # it without certs causes silent connection failures for restricted clients.
        if settings.FILE_SHARING_TURN_TLS_ENABLED:
            turn_urls.append(
                f"turns:{settings.FILE_SHARING_TURN_HOST}:{settings.FILE_SHARING_TURN_TLS_PORT}"
            )

        ice_servers.append(
            ICEServer(
                urls=turn_urls,
                username=username,
                credential=credential,
            )
        )

    return ICEConfigResponse(
        ice_servers=ice_servers,
    )


# ── Authenticated Session Detail / Reports (PG-backed) ──


async def get_session_detail(
    session: AsyncReadSession,
    auth_subject: AuthPrincipal[User | Workspace],
    *,
    session_id: UUID,
) -> "FileShareSession | None":
    """Get a file share session with auth check, or None if not found/not accessible."""

    repo = FileShareSessionRepository.from_session(session)
    statement = repo.get_readable_statement(auth_subject)
    statement = statement.where(FileShareSession.id == session_id)
    return await repo.get_one_or_none(statement)


async def get_session_detail_with_relations(
    session: AsyncReadSession,
    auth_subject: AuthPrincipal[User | Workspace],
    *,
    session_id: UUID,
) -> tuple[FileShareSession, list[Any], list[Any], list[Any]] | None:
    """Get a file share session with payments, downloads, and reports.

    Returns (session, payments, downloads, reports) or None if not found.
    """
    fs_session = await get_session_detail(session, auth_subject, session_id=session_id)
    if fs_session is None:
        return None

    payment_repo = FileSharePaymentRepository.from_session(session)
    payments = await payment_repo.get_by_session_id(session_id)

    download_repo = FileShareDownloadRepository.from_session(session)
    downloads = await download_repo.get_by_session_id(session_id)

    report_repo = FileShareReportRepository.from_session(session)
    reports = await report_repo.get_by_session_id(session_id)

    return fs_session, payments, downloads, reports


async def get_session_reports(
    session: AsyncReadSession,
    auth_subject: AuthPrincipal[User | Workspace],
    *,
    session_id: UUID,
) -> list[FileShareReport] | None:
    """Get reports for a session after verifying access."""
    fs_session = await get_session_detail(session, auth_subject, session_id=session_id)
    if fs_session is None:
        return None  # Caller should raise 404

    report_repo = FileShareReportRepository.from_session(session)
    return await report_repo.get_by_session_id(session_id)


async def update_session_report(
    session: "AsyncSession",
    auth_subject: AuthPrincipal[User | Workspace],
    *,
    report_id: UUID,
    status: FileShareReportStatus,
    admin_notes: str | None = None,
) -> "FileShareReport | None":
    """Update a report status. Returns None if report/session not found.

    If status is 'actioned', also destroys the associated session.
    """
    report_repo = FileShareReportRepository.from_session(session)
    report = await report_repo.get_by_id(report_id)
    if report is None:
        return None

    # Verify the session belongs to the user's workspace
    session_repo = FileShareSessionRepository.from_session(session)
    readable = session_repo.get_readable_statement(auth_subject)
    readable = readable.where(FileShareSession.id == report.session_id)
    fs_session = await session_repo.get_one_or_none(readable)
    if fs_session is None:
        return None

    update_dict: dict[str, Any] = {
        "status": status,
        "reviewed_at": now_utc(),
    }
    if admin_notes is not None:
        update_dict["admin_notes"] = admin_notes

    await report_repo.update(report, update_dict=update_dict, flush=True)

    # If actioned, also destroy the session
    if status == FileShareReportStatus.actioned:
        if fs_session.status != FileShareSessionStatus.destroyed:
            await session_repo.update(
                fs_session,
                update_dict={
                    "status": FileShareSessionStatus.destroyed,
                    "completed_at": now_utc(),
                },
                flush=True,
            )

    return report


# ── Public Stats ──


_STATS_CACHE_KEY = "file-sharing:stats:cached_total"
_STATS_CACHE_TTL = 15  # seconds


async def get_public_stats(session: AsyncReadSession, redis: Redis) -> int:
    """Return total share count (PG sessions + Redis secrets/files) for the landing page.

    Results are cached in Redis for 15 seconds to avoid hitting PG on every poll.
    """
    cached = await redis.get(_STATS_CACHE_KEY)
    if cached is not None:
        return int(cached)

    pg_repo = FileShareSessionRepository.from_session(session)
    secret_repo = SecretRepository(redis)
    pg_count = await pg_repo.get_total_count()
    secret_count = await secret_repo.get_created_count()
    total = pg_count + secret_count

    await redis.setex(_STATS_CACHE_KEY, _STATS_CACHE_TTL, str(total))
    return total


async def get_workspace_stats(
    session: AsyncReadSession, redis: Redis, workspace_id: UUID
) -> int:
    """Return combined share count (PG sessions + Redis secrets) for a workspace."""
    pg_repo = FileShareSessionRepository.from_session(session)
    secret_repo = SecretRepository(redis)
    pg_count = await pg_repo.get_count_by_workspace(workspace_id)
    secret_count = await secret_repo.get_workspace_created_count(str(workspace_id))
    return pg_count + secret_count


# ── Authenticated Session List (PG-backed) ──


async def list_sessions(
    session: AsyncReadSession,
    auth_subject: AuthPrincipal[User | Workspace],
    *,
    pagination: PaginationParams,
    sorting: list[Any] | None = None,
    status: str | None = None,
    query: str | None = None,
    workspace_id: UUID | None = None,
) -> tuple[list[Any], int]:
    """List file sharing sessions from PG for authenticated users."""
    repo = FileShareSessionRepository.from_session(session)
    statement = repo.get_readable_statement(auth_subject)
    statement = repo.apply_list_filters(
        statement, status=status, query=query, workspace_id=workspace_id
    )

    if sorting:
        statement = repo.apply_sorting(statement, sorting)
    else:
        statement = statement.order_by(FileShareSession.created_at.desc())

    return await repo.paginate(statement, limit=pagination.limit, page=pagination.page)
