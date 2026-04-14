"""File sharing API endpoints."""

from typing import NoReturn
from uuid import UUID

import structlog
from fastapi import Depends, Header, HTTPException, Query, Request, Response, WebSocket

from rapidly.config import settings
from rapidly.core.db.postgres import AsyncReadSession
from rapidly.core.geolocation import get_request_geo
from rapidly.core.pagination import PaginatedList, PaginationParamsQuery
from rapidly.errors import BadRequest, NotPermitted, ResourceNotFound, Unauthorized
from rapidly.identity.auth.dependencies import WebUserOrAnonymous
from rapidly.openapi import APITag
from rapidly.postgres import AsyncSession, get_db_read_session, get_db_session
from rapidly.posthog import posthog
from rapidly.redis import Redis, get_redis
from rapidly.routing import APIRouter

from . import actions as file_sharing_service
from . import ordering
from .guards import (
    CHANNEL_ACTION_RATE_LIMIT,
    CHANNEL_ACTION_RATE_WINDOW,
    CHANNEL_CREATE_RATE_LIMIT,
    CHANNEL_CREATE_RATE_WINDOW,
    CHANNEL_FETCH_RATE_LIMIT,
    CHANNEL_FETCH_RATE_WINDOW,
    SECRET_CREATE_RATE_LIMIT,
    SECRET_CREATE_RATE_WINDOW,
    SECRET_FETCH_RATE_LIMIT,
    SECRET_FETCH_RATE_WINDOW,
    SECRET_METADATA_RATE_LIMIT,
    SECRET_METADATA_RATE_WINDOW,
    check_body_size,
    check_rate_limit,
    extract_bearer_token,
    get_redis_ws,
    validate_slug,
)
from .permissions import FileSharingRead, FileSharingWrite
from .queries import _decrypt_token, _encrypt_token
from .signaling import handle_signaling
from .types import (
    ChannelCheckoutRequest,
    ChannelCheckoutResponse,
    ChannelCreateRequest,
    ChannelCreateResponse,
    ChannelDestroyRequest,
    ChannelDestroyResponse,
    ChannelFetchResponse,
    ChannelRenewRequest,
    ChannelRenewResponse,
    ChecksumFetchResponse,
    ChecksumUploadRequest,
    ChecksumUploadResponse,
    ClaimPaymentTokenRequest,
    DirectPaymentResponse,
    DownloadCompleteRequest,
    DownloadCompleteResponse,
    FileSecretCreateRequest,
    FileShareDownloadSchema,
    FileSharePaymentSchema,
    FileShareReportSchema,
    FileShareSessionDetailSchema,
    FileShareSessionSchema,
    FileShareStatsResponse,
    ICEConfigRequest,
    ICEConfigResponse,
    PasswordAttemptRequest,
    PasswordAttemptResponse,
    ReaderTokenRequest,
    ReaderTokenResponse,
    ReportRequest,
    ReportResponse,
    ReportUpdateRequest,
    SecretCheckoutResponse,
    SecretCreateRequest,
    SecretCreateResponse,
    SecretFetchResponse,
    SecretMetadataResponse,
)
from .utils import hash_ip

_log = structlog.get_logger(__name__)

_CREATION_ERROR_MAP = {401: Unauthorized, 403: NotPermitted}


def _read_payment_cookie(request: Request, cookie_name: str) -> str | None:
    """Read and decrypt a payment token from an httpOnly cookie."""
    encrypted = request.cookies.get(cookie_name)
    if not encrypted:
        return None
    try:
        return _decrypt_token(encrypted)
    except Exception:
        return None


def _raise_creation_error(e: file_sharing_service.ChannelCreationError) -> NoReturn:
    """Map a ChannelCreationError to the appropriate HTTP exception."""
    error_cls = _CREATION_ERROR_MAP.get(e.status_code, BadRequest)
    raise error_cls(e.detail)


router = APIRouter(prefix="/file-sharing", tags=["file-sharing", APITag.public])


# ── Public Stats ──


@router.get("/stats", response_model=FileShareStatsResponse)
async def get_stats(
    http_request: Request,
    workspace_id: UUID | None = Query(
        None, description="Optional workspace ID for workspace-scoped counts."
    ),
    redis: Redis = Depends(get_redis),
    session: AsyncReadSession = Depends(get_db_read_session),
) -> FileShareStatsResponse:
    """Public endpoint returning total file share count for the landing page.

    When ``workspace_id`` is provided, returns the combined count of
    file-share sessions **and** secrets created under that workspace.
    """
    await check_rate_limit(
        http_request,
        redis,
        "stats",
        CHANNEL_FETCH_RATE_LIMIT,
        CHANNEL_FETCH_RATE_WINDOW,
    )
    if workspace_id:
        total = await file_sharing_service.get_workspace_stats(
            session, redis, workspace_id
        )
    else:
        total = await file_sharing_service.get_public_stats(session, redis)
    return FileShareStatsResponse(total_shares=total)


# ── Session Listing and Detail ──


@router.get("/sessions", response_model=PaginatedList[FileShareSessionSchema])
async def list_sessions(
    auth_subject: FileSharingRead,
    pagination: PaginationParamsQuery,
    sorting: ordering.ListSorting,
    status: str | None = Query(
        None,
        description="Filter by session status (created, active, completed, expired, destroyed, reported).",
    ),
    query: str | None = Query(None, description="Search by file name or slug."),
    workspace_id: UUID | None = Query(None, description="Filter by workspace ID."),
    session: AsyncReadSession = Depends(get_db_read_session),
) -> PaginatedList[FileShareSessionSchema]:
    """List file sharing sessions for the authenticated user/workspace."""
    results, count = await file_sharing_service.list_sessions(
        session,
        auth_subject,
        pagination=pagination,
        sorting=sorting,
        status=status,
        query=query,
        workspace_id=workspace_id,
    )
    return PaginatedList.from_paginated_results(results, count, pagination)


@router.get("/sessions/{session_id}", response_model=FileShareSessionDetailSchema)
async def get_session(
    session_id: UUID,
    auth_subject: FileSharingRead,
    http_request: Request,
    redis: Redis = Depends(get_redis),
    session: AsyncReadSession = Depends(get_db_read_session),
) -> FileShareSessionDetailSchema:
    """Get detailed info for a single file sharing session."""
    await check_rate_limit(
        http_request,
        redis,
        "session_detail",
        CHANNEL_FETCH_RATE_LIMIT,
        CHANNEL_FETCH_RATE_WINDOW,
    )
    result = await file_sharing_service.get_session_detail_with_relations(
        session, auth_subject, session_id=session_id
    )
    if result is None:
        raise ResourceNotFound("Session not found")

    fs_session, payments, downloads, reports = result

    detail = FileShareSessionDetailSchema.model_validate(
        fs_session, from_attributes=True
    )
    detail.payments = [
        FileSharePaymentSchema.model_validate(p, from_attributes=True) for p in payments
    ]
    detail.downloads = [
        FileShareDownloadSchema.model_validate(d, from_attributes=True)
        for d in downloads
    ]
    detail.reports = [
        FileShareReportSchema.model_validate(r, from_attributes=True) for r in reports
    ]
    return detail


# ── Reporting ──


@router.get(
    "/sessions/{session_id}/reports",
    response_model=list[FileShareReportSchema],
)
async def list_session_reports(
    session_id: UUID,
    auth_subject: FileSharingRead,
    session: AsyncReadSession = Depends(get_db_read_session),
) -> list[FileShareReportSchema]:
    """List reports for a file sharing session."""
    reports = await file_sharing_service.get_session_reports(
        session, auth_subject, session_id=session_id
    )
    if reports is None:
        raise ResourceNotFound("Session not found")
    return [
        FileShareReportSchema.model_validate(r, from_attributes=True) for r in reports
    ]


@router.patch(
    "/reports/{report_id}",
    response_model=FileShareReportSchema,
)
async def update_report(
    report_id: UUID,
    report_update: ReportUpdateRequest,
    auth_subject: FileSharingWrite,
    session: AsyncSession = Depends(get_db_session),
) -> FileShareReportSchema:
    """Update a report status (review, dismiss, or action)."""
    if report_update.status is None:
        raise BadRequest("status is required")
    report = await file_sharing_service.update_session_report(
        session,
        auth_subject,
        report_id=report_id,
        status=report_update.status,
        admin_notes=report_update.admin_notes,
    )
    if report is None:
        raise ResourceNotFound("Report not found")
    return FileShareReportSchema.model_validate(report, from_attributes=True)


# ── WebRTC Signaling ──


@router.websocket("/signal/{slug:path}")
async def websocket_signal(
    ws: WebSocket,
    slug: str,
    redis: Redis = Depends(get_redis_ws),
) -> None:
    """WebSocket signaling endpoint for WebRTC peer connections.

    Replaces the third-party PeerJS signaling server. Authenticates
    peers via first-message auth (not query params) to avoid log leakage.

    Note: Slug validation happens after ws.accept() because ASGI/Starlette
    requires accepting the WebSocket before sending close frames. The
    per-IP rate limiter in handle_signaling() mitigates resource exhaustion
    from invalid slug connections.
    """
    await ws.accept()
    try:
        slug = validate_slug(slug)
    except HTTPException:
        await ws.close(code=4001, reason="Invalid slug format")
        return
    await handle_signaling(ws, slug, redis)


# ── Secret Sharing ──


@router.post("/secret", response_model=SecretCreateResponse, status_code=201)
async def create_secret(
    request: SecretCreateRequest,
    http_request: Request,
    auth_subject: WebUserOrAnonymous,
    redis: Redis = Depends(get_redis),
    session: AsyncReadSession = Depends(get_db_read_session),
) -> SecretCreateResponse:
    """Create a new encrypted text secret.

    Stores an OpenPGP encrypted message. The decryption key is never
    sent to the server - it should be included in the URL on the client side.
    Secrets are always one-time and deleted after first retrieval.

    For paid secrets (price_cents > 0), the user must be authenticated
    and a member of the specified workspace.
    """
    await check_body_size(http_request)
    await check_rate_limit(
        http_request,
        redis,
        "secret_create",
        SECRET_CREATE_RATE_LIMIT,
        SECRET_CREATE_RATE_WINDOW,
    )
    try:
        currency = (
            request.currency
            or await file_sharing_service.resolve_workspace_currency(
                session, request.workspace_id
            )
        )
        return await file_sharing_service.create_secret_or_file(
            redis=redis,
            kind="secret",
            message=request.message,
            expiration=request.expiration,
            workspace_id=request.workspace_id,
            price_cents=request.price_cents,
            currency=currency,
            title=request.title,
            auth_subject=auth_subject,
            read_session=session,
        )
    except file_sharing_service.ChannelCreationError as e:
        _raise_creation_error(e)


@router.get("/secret/{secret_id}/metadata", response_model=SecretMetadataResponse)
async def get_secret_metadata(
    secret_id: UUID,
    http_request: Request,
    redis: Redis = Depends(get_redis),
) -> SecretMetadataResponse:
    """Peek at secret metadata (title, payment info) without consuming it."""
    await check_rate_limit(
        http_request,
        redis,
        "secret_metadata",
        SECRET_METADATA_RATE_LIMIT,
        SECRET_METADATA_RATE_WINDOW,
    )
    result = await file_sharing_service.peek_secret_metadata(
        redis=redis,
        secret_id=str(secret_id),
    )
    if result is None:
        raise ResourceNotFound("Secret not found")
    return result


@router.get("/secret/{secret_id}", response_model=SecretFetchResponse)
async def fetch_secret(
    secret_id: UUID,
    http_request: Request,
    redis: Redis = Depends(get_redis),
    x_payment_token: str | None = Header(None),
) -> SecretFetchResponse:
    """Fetch an encrypted text secret.

    Returns the encrypted message and deletes it from storage.
    The secret can only be retrieved once. For paid secrets, a payment
    token (via header or cookie) is required.
    """
    await check_rate_limit(
        http_request,
        redis,
        "secret_fetch",
        SECRET_FETCH_RATE_LIMIT,
        SECRET_FETCH_RATE_WINDOW,
    )
    payment_token = x_payment_token or _read_payment_cookie(http_request, "rapidly_spt")
    client_ip = http_request.client.host if http_request.client else "unknown"
    buyer_fingerprint = hash_ip(client_ip)
    result = await file_sharing_service.fetch_secret_or_file(
        redis=redis,
        kind="secret",
        item_id=str(secret_id),
        payment_token=payment_token,
        buyer_fingerprint=buyer_fingerprint,
    )
    if result is None:
        raise ResourceNotFound("Secret not found")
    return result


# ── File Sharing (Encrypted Files) ──


@router.post("/file", response_model=SecretCreateResponse, status_code=201)
async def create_file_secret(
    request: FileSecretCreateRequest,
    http_request: Request,
    auth_subject: WebUserOrAnonymous,
    redis: Redis = Depends(get_redis),
    session: AsyncReadSession = Depends(get_db_read_session),
) -> SecretCreateResponse:
    """Create a new encrypted file secret.

    Stores an OpenPGP encrypted file. The decryption key is never
    sent to the server - it should be included in the URL on the client side.
    Files are always one-time and deleted after first retrieval.

    For paid files (price_cents > 0), the user must be authenticated
    and a member of the specified workspace.
    """
    await check_body_size(http_request)
    await check_rate_limit(
        http_request,
        redis,
        "secret_create",
        SECRET_CREATE_RATE_LIMIT,
        SECRET_CREATE_RATE_WINDOW,
    )
    try:
        currency = (
            request.currency
            or await file_sharing_service.resolve_workspace_currency(
                session, request.workspace_id
            )
        )
        return await file_sharing_service.create_secret_or_file(
            redis=redis,
            kind="file",
            message=request.message,
            expiration=request.expiration,
            workspace_id=request.workspace_id,
            price_cents=request.price_cents,
            currency=currency,
            title=request.title,
            auth_subject=auth_subject,
            read_session=session,
        )
    except file_sharing_service.ChannelCreationError as e:
        _raise_creation_error(e)


@router.get("/file/{file_id}", response_model=SecretFetchResponse)
async def fetch_file_secret(
    file_id: UUID,
    http_request: Request,
    redis: Redis = Depends(get_redis),
    x_payment_token: str | None = Header(None),
) -> SecretFetchResponse:
    """Fetch an encrypted file secret.

    Returns the encrypted file and deletes it from storage.
    The file can only be retrieved once. For paid files, a payment
    token (via header or cookie) is required.
    """
    await check_rate_limit(
        http_request,
        redis,
        "secret_fetch",
        SECRET_FETCH_RATE_LIMIT,
        SECRET_FETCH_RATE_WINDOW,
    )
    payment_token = x_payment_token or _read_payment_cookie(http_request, "rapidly_spt")
    client_ip = http_request.client.host if http_request.client else "unknown"
    buyer_fingerprint = hash_ip(client_ip)
    result = await file_sharing_service.fetch_secret_or_file(
        redis=redis,
        kind="file",
        item_id=str(file_id),
        payment_token=payment_token,
        buyer_fingerprint=buyer_fingerprint,
    )
    if result is None:
        raise ResourceNotFound("Secret not found")
    return result


# ── Secret Payments (Checkout) ──


@router.post(
    "/secrets/{secret_id}/checkout",
    response_model=SecretCheckoutResponse,
    status_code=201,
)
async def create_secret_checkout(
    secret_id: UUID,
    http_request: Request,
    redis: Redis = Depends(get_redis),
) -> SecretCheckoutResponse:
    """Create a Stripe Checkout Session for a paid secret.

    Returns a checkout URL to redirect the buyer to Stripe.
    """
    await check_rate_limit(
        http_request,
        redis,
        "checkout",
        CHANNEL_ACTION_RATE_LIMIT,
        CHANNEL_ACTION_RATE_WINDOW,
    )
    client_ip = http_request.client.host if http_request.client else "unknown"
    buyer_fingerprint = hash_ip(client_ip)
    try:
        result = await file_sharing_service.create_secret_checkout(
            redis=redis,
            secret_id=str(secret_id),
            buyer_fingerprint=buyer_fingerprint,
        )
    except ValueError as e:
        raise BadRequest(str(e))
    if result is None:
        raise ResourceNotFound("Secret not found")
    return result


@router.post(
    "/secrets/{secret_id}/claim-payment-token",
    status_code=200,
)
async def claim_secret_payment_token(
    secret_id: UUID,
    request: ClaimPaymentTokenRequest,
    http_request: Request,
    response: Response,
    redis: Redis = Depends(get_redis),
) -> dict[str, bool]:
    """Exchange a Stripe checkout session ID for the secret payment token.

    One-time use — the token can only be claimed once.
    The token is delivered ONLY via an httpOnly cookie (never in the response body)
    to prevent exfiltration by third-party scripts.
    """
    await check_rate_limit(
        http_request,
        redis,
        "claim_token",
        CHANNEL_ACTION_RATE_LIMIT,
        CHANNEL_ACTION_RATE_WINDOW,
    )
    token = await file_sharing_service.claim_secret_checkout_payment_token(
        redis=redis,
        secret_id=str(secret_id),
        checkout_session_id=request.checkout_session_id,
    )
    if token is None:
        raise ResourceNotFound("Invalid or already claimed checkout session")

    response.set_cookie(
        "rapidly_spt",
        value=_encrypt_token(token),
        max_age=3600,
        httponly=True,
        secure=not settings.is_development(),
        samesite="strict",
        path="/api/file-sharing/",
    )

    return {"success": True}


# ── Channel Lifecycle ──


@router.post("/channels", response_model=ChannelCreateResponse, status_code=201)
async def create_channel(
    request: ChannelCreateRequest,
    http_request: Request,
    auth_subject: WebUserOrAnonymous,
    redis: Redis = Depends(get_redis),
    read_session: AsyncReadSession = Depends(get_db_read_session),
    write_session: AsyncSession = Depends(get_db_session),
) -> ChannelCreateResponse:
    """Create a new file sharing channel.

    Creates a channel with unique short and long slugs that can be used
    to share files. Returns a secret that must be used for renewal.
    Rate limited to prevent abuse.

    For paid channels (price_cents > 0), the user must be authenticated
    and have an active Stripe Connect account with charges enabled.
    A share record is also created to track the sale.
    """
    await check_rate_limit(
        http_request,
        redis,
        "channel_create",
        CHANNEL_CREATE_RATE_LIMIT,
        CHANNEL_CREATE_RATE_WINDOW,
        detail="Too many channels created. Try again later.",
    )

    currency = (
        request.currency
        or await file_sharing_service.resolve_workspace_currency(
            read_session, request.workspace_id
        )
    )

    try:
        (
            user_id,
            workspace_id,
            seller_stripe_id,
            seller_account_id,
        ) = await file_sharing_service.resolve_channel_creation_context(
            read_session,
            auth_subject,
            workspace_id_input=request.workspace_id,
            price_cents=request.price_cents,
            currency=currency,
            redis=redis,
        )
    except file_sharing_service.ChannelCreationError as e:
        _raise_creation_error(e)

    client_ip = http_request.client.host if http_request.client else "unknown"
    creator_ip_hash = hash_ip(client_ip)
    geo = get_request_geo(http_request)

    result = await file_sharing_service.create_channel(
        redis=redis,
        max_downloads=request.max_downloads,
        price_cents=request.price_cents,
        currency=currency,
        seller_stripe_id=seller_stripe_id,
        seller_account_id=seller_account_id,
        user_id=user_id,
        title=request.title,
        file_name=request.file_name,
        file_size_bytes=request.file_size_bytes,
        session=write_session,
        workspace_id=workspace_id,
        creator_ip_hash=creator_ip_hash,
        creator_country=geo.country,
        creator_continent=geo.continent,
    )

    # Server-side analytics event with geolocation
    posthog.capture(
        distinct_id=user_id or creator_ip_hash,
        event="file_sharing:channel:create",
        properties={
            "$geoip_country_code": geo.country,
            "$geoip_continent_code": geo.continent,
            "is_paid": request.price_cents is not None and request.price_cents > 0,
            "file_name": request.file_name,
        },
    )

    return result


@router.get("/channels/{slug:path}", response_model=ChannelFetchResponse)
async def fetch_channel(
    slug: str,
    http_request: Request,
    authorization: str | None = Header(None),
    x_payment_token: str | None = Header(None, alias="X-Payment-Token"),
    redis: Redis = Depends(get_redis),
) -> ChannelFetchResponse:
    """Check channel availability for downloading.

    Returns whether the channel is available (has download slots remaining).
    The slug can be either short (a1b2c3d4) or long (bacon/cheese/tomato/onion).
    Peer discovery happens via WebSocket signaling, not this endpoint.

    If a reader token is registered for the channel, an Authorization header
    with ``Bearer <token>`` must be provided. This prevents slug enumeration
    and keeps the token out of server access logs.

    For paid channels, pass ``X-Payment-Token`` header to check payment status.

    Rate limited to prevent brute-force slug enumeration.
    """
    await check_rate_limit(
        http_request,
        redis,
        "channel_fetch",
        CHANNEL_FETCH_RATE_LIMIT,
        CHANNEL_FETCH_RATE_WINDOW,
    )

    slug = validate_slug(slug)

    token = extract_bearer_token(authorization)

    # Accept payment token from header OR httpOnly cookie (encrypted at rest)
    effective_payment_token = x_payment_token or _read_payment_cookie(
        http_request, "rapidly_pt"
    )

    client_ip = http_request.client.host if http_request.client else "unknown"
    result = await file_sharing_service.fetch_channel(
        redis=redis,
        slug=slug,
        reader_token=token,
        payment_token=effective_payment_token,
        buyer_fingerprint=hash_ip(client_ip),
    )
    if result is None:
        raise ResourceNotFound("Channel not found")
    return result


# ── Payments (Checkout) ──


@router.post(
    "/channels/{slug:path}/checkout",
    response_model=ChannelCheckoutResponse | DirectPaymentResponse,
    status_code=201,
)
async def create_checkout(
    slug: str,
    http_request: Request,
    auth_subject: WebUserOrAnonymous,
    body: ChannelCheckoutRequest | None = None,
    redis: Redis = Depends(get_redis),
    session: AsyncSession = Depends(get_db_session),
) -> ChannelCheckoutResponse | DirectPaymentResponse:
    """Create a Stripe Checkout Session or direct PaymentIntent for a paid channel.

    If ``payment_method_id`` is provided in the request body, charges the
    saved card directly via PaymentIntent (no Stripe Checkout redirect).
    Requires authentication when using a saved payment method.
    """
    slug = validate_slug(slug)
    await check_rate_limit(
        http_request,
        redis,
        "checkout",
        CHANNEL_ACTION_RATE_LIMIT,
        CHANNEL_ACTION_RATE_WINDOW,
    )
    client_ip = http_request.client.host if http_request.client else "unknown"
    buyer_fingerprint = hash_ip(client_ip)
    payment_method_id = body.payment_method_id if body else None

    # Resolve authenticated buyer's customer ID for ownership verification.
    # Anonymous users or non-customer principals fall through to Checkout Session.
    buyer_customer_id: UUID | None = None
    if payment_method_id is not None:
        from rapidly.identity.auth.models import Anonymous

        subject = auth_subject.subject
        if isinstance(subject, Anonymous):
            # Anonymous users can't use saved cards — fall through to checkout
            payment_method_id = None
        else:
            # Look up the payment method to find the owning customer
            # The actual ownership check happens in create_checkout via buyer_customer_id
            from rapidly.billing.payment_method import actions as pm_actions

            pm = await pm_actions.get(session, payment_method_id)
            if pm is not None:
                buyer_customer_id = pm.customer_id
            else:
                payment_method_id = None  # Invalid PM — fall through to checkout

    try:
        result = await file_sharing_service.create_checkout(
            redis=redis,
            slug=slug,
            session=session,
            buyer_fingerprint=buyer_fingerprint,
            payment_method_id=payment_method_id,
            buyer_customer_id=buyer_customer_id,
        )
    except ValueError as e:
        raise BadRequest(str(e))
    if result is None:
        raise ResourceNotFound("Channel not found")
    return result


# ── Channel Authorization (Reader Token / Password) ──


@router.post(
    "/channels/{slug:path}/reader-token",
    response_model=ReaderTokenResponse,
    status_code=201,
)
async def set_reader_token(
    slug: str,
    request: ReaderTokenRequest,
    http_request: Request,
    redis: Redis = Depends(get_redis),
) -> ReaderTokenResponse:
    """Register a reader authorization token for a channel.

    Requires the channel secret. Once set, downloaders must provide the
    matching reader token when fetching channel info. This prevents slug
    enumeration attacks.
    """
    slug = validate_slug(slug)
    await check_rate_limit(
        http_request,
        redis,
        "set_reader_token",
        CHANNEL_ACTION_RATE_LIMIT,
        CHANNEL_ACTION_RATE_WINDOW,
    )
    return await file_sharing_service.set_reader_token(
        redis=redis,
        slug=slug,
        secret=request.secret,
        token_hash=request.token_hash,
    )


@router.post(
    "/channels/{slug:path}/password-attempt",
    response_model=PasswordAttemptResponse,
    status_code=200,
)
async def record_password_attempt(
    slug: str,
    request: PasswordAttemptRequest,
    http_request: Request,
    redis: Redis = Depends(get_redis),
) -> PasswordAttemptResponse:
    """Record a password attempt for rate limiting.

    Tracks password attempts server-side as defense-in-depth against brute-force.
    Requires the channel secret to prove the caller is the uploader.
    Returns whether the attempt is allowed and how many remain.
    """
    slug = validate_slug(slug)
    await check_rate_limit(
        http_request,
        redis,
        "password_attempt",
        CHANNEL_ACTION_RATE_LIMIT,
        CHANNEL_ACTION_RATE_WINDOW,
    )
    return await file_sharing_service.record_password_attempt(
        redis=redis,
        slug=slug,
        secret=request.secret,
    )


@router.post(
    "/channels/{slug:path}/claim-payment-token",
    status_code=200,
)
async def claim_payment_token(
    slug: str,
    request: ClaimPaymentTokenRequest,
    http_request: Request,
    response: Response,
    redis: Redis = Depends(get_redis),
) -> dict[str, bool]:
    """Exchange a Stripe checkout session ID for the payment token.

    One-time use — the token can only be claimed once. Called by the
    frontend after a Stripe checkout redirect to retrieve the payment
    token without exposing it in the URL.

    The token is delivered ONLY via an httpOnly cookie (never in the
    response body) to prevent exfiltration by third-party scripts.
    """
    slug = validate_slug(slug)
    await check_rate_limit(
        http_request,
        redis,
        "claim_token",
        CHANNEL_ACTION_RATE_LIMIT,
        CHANNEL_ACTION_RATE_WINDOW,
    )
    token = await file_sharing_service.claim_checkout_payment_token(
        redis=redis,
        slug=slug,
        checkout_session_id=request.checkout_session_id,
    )
    if token is None:
        raise ResourceNotFound("Invalid or already claimed checkout session")

    # Set payment token in httpOnly cookie so JS never touches it.
    # The cookie is sent automatically with subsequent HTTP and WS requests.
    response.set_cookie(
        "rapidly_pt",
        value=_encrypt_token(token),
        max_age=3600,  # 1 hour — matches frontend PAYMENT_TOKEN_TTL_MS
        httponly=True,
        secure=not settings.is_development(),
        samesite="strict",
        path="/api/file-sharing/",
    )

    return {"success": True}


# ── Checksums ──


@router.post(
    "/channels/{slug:path}/checksums",
    response_model=ChecksumUploadResponse,
    status_code=201,
)
async def upload_checksums(
    slug: str,
    request: ChecksumUploadRequest,
    http_request: Request,
    redis: Redis = Depends(get_redis),
) -> ChecksumUploadResponse:
    """Upload SHA-256 checksums for a channel's files.

    Requires the channel secret. Stores checksums in Redis alongside channel
    data so downloaders can verify file integrity after download.
    """
    slug = validate_slug(slug)
    await check_rate_limit(
        http_request,
        redis,
        "checksums_upload",
        CHANNEL_ACTION_RATE_LIMIT,
        CHANNEL_ACTION_RATE_WINDOW,
    )
    return await file_sharing_service.upload_checksums(
        redis=redis,
        slug=slug,
        secret=request.secret,
        checksums=request.checksums,
    )


@router.get(
    "/channels/{slug:path}/checksums",
    response_model=ChecksumFetchResponse,
)
async def fetch_checksums(
    slug: str,
    http_request: Request,
    authorization: str | None = Header(None),
    redis: Redis = Depends(get_redis),
) -> ChecksumFetchResponse:
    """Fetch SHA-256 checksums for a channel's files.

    Requires a valid reader token via Authorization header.
    Returns a map of fileName to SHA-256 hex digest.
    """
    slug = validate_slug(slug)
    await check_rate_limit(
        http_request,
        redis,
        "checksums_fetch",
        CHANNEL_FETCH_RATE_LIMIT,
        CHANNEL_FETCH_RATE_WINDOW,
    )

    token = extract_bearer_token(authorization)
    if not token:
        raise Unauthorized("Reader token required")

    result = await file_sharing_service.fetch_checksums(
        redis=redis, slug=slug, reader_token=token
    )
    if result is None:
        raise ResourceNotFound("Checksums not found")
    return result


# ── Downloads ──


@router.post(
    "/channels/{slug:path}/download-complete",
    response_model=DownloadCompleteResponse,
    status_code=200,
)
async def record_download_complete(
    slug: str,
    request: DownloadCompleteRequest,
    http_request: Request,
    redis: Redis = Depends(get_redis),
    session: AsyncSession = Depends(get_db_session),
) -> DownloadCompleteResponse:
    """Record a completed download for server-side limit enforcement.

    Increments the download counter. Requires a valid reader token.
    Returns whether the recording succeeded and how many downloads remain.
    """
    slug = validate_slug(slug)
    await check_rate_limit(
        http_request,
        redis,
        "download_complete",
        CHANNEL_ACTION_RATE_LIMIT,
        CHANNEL_ACTION_RATE_WINDOW,
    )
    client_ip = http_request.client.host if http_request.client else "unknown"
    return await file_sharing_service.record_download_complete(
        redis=redis,
        slug=slug,
        reader_token=request.token,
        session=session,
        downloader_ip_hash=hash_ip(client_ip),
    )


@router.post(
    "/channels/{slug:path}/renew", response_model=ChannelRenewResponse, status_code=200
)
async def renew_channel(
    slug: str,
    request: ChannelRenewRequest,
    http_request: Request,
    redis: Redis = Depends(get_redis),
    session: AsyncSession = Depends(get_db_session),
) -> ChannelRenewResponse:
    """Renew a channel's TTL.

    Extends the channel's expiration time. Requires the channel secret.
    """
    slug = validate_slug(slug)
    await check_rate_limit(
        http_request,
        redis,
        "renew",
        CHANNEL_ACTION_RATE_LIMIT,
        CHANNEL_ACTION_RATE_WINDOW,
    )
    result = await file_sharing_service.renew_channel(
        redis=redis,
        slug=slug,
        secret=request.secret,
        session=session,
    )
    if not result.success:
        raise NotPermitted("Invalid channel secret")
    return result


@router.post(
    "/channels/{slug:path}/destroy",
    response_model=ChannelDestroyResponse,
)
async def destroy_channel(
    slug: str,
    request: ChannelDestroyRequest,
    http_request: Request,
    redis: Redis = Depends(get_redis),
    session: AsyncSession = Depends(get_db_session),
) -> ChannelDestroyResponse:
    """Request channel destruction (authenticated).

    Requires the channel ownership secret to prevent unauthorized destruction.
    Used by the uploader when closing the page or explicitly ending the session.

    - First request: Marks channel for destruction with 30-second delay
    - Second request: Confirms immediate destruction
    - Channel owner can cancel by renewing the channel
    """
    slug = validate_slug(slug)
    await check_rate_limit(
        http_request,
        redis,
        "destroy",
        CHANNEL_ACTION_RATE_LIMIT,
        CHANNEL_ACTION_RATE_WINDOW,
    )
    result = await file_sharing_service.destroy_channel(
        redis=redis, slug=slug, secret=request.secret, session=session
    )
    if not result.success:
        raise NotPermitted("Invalid channel secret")
    return result


# ── Channel Reporting ──


@router.post(
    "/channels/{slug:path}/report",
    response_model=ReportResponse,
    status_code=201,
)
async def report_channel(
    slug: str,
    request: ReportRequest,
    http_request: Request,
    redis: Redis = Depends(get_redis),
    session: AsyncSession = Depends(get_db_session),
) -> ReportResponse:
    """Report a channel for terms violation.

    Closes the signaling room to prevent new peer connections.
    Requires a valid reader token if one is registered for the channel.
    """
    slug = validate_slug(slug)
    await check_rate_limit(
        http_request,
        redis,
        "report",
        CHANNEL_ACTION_RATE_LIMIT,
        CHANNEL_ACTION_RATE_WINDOW,
    )
    client_ip = http_request.client.host if http_request.client else "unknown"
    return await file_sharing_service.report_channel(
        redis=redis,
        slug=slug,
        reader_token=request.token,
        session=session,
        reporter_ip_hash=hash_ip(client_ip),
    )


# ── ICE / WebRTC Configuration ──


@router.post("/ice/{slug:path}", response_model=ICEConfigResponse)
async def get_ice_config(
    slug: str,
    request: ICEConfigRequest,
    http_request: Request,
    redis: Redis = Depends(get_redis),
) -> ICEConfigResponse:
    """Get ICE server configuration for WebRTC.

    Returns STUN/TURN server configuration. Requires a valid channel slug
    and reader token to prevent unauthenticated TURN credential harvesting.
    Signaling delivers ICE config automatically in the welcome message;
    this endpoint is a fallback.
    """
    slug = validate_slug(slug)
    await check_rate_limit(
        http_request,
        redis,
        "ice_config",
        CHANNEL_ACTION_RATE_LIMIT,
        CHANNEL_ACTION_RATE_WINDOW,
    )
    try:
        result = await file_sharing_service.get_ice_config_for_channel(
            redis=redis, slug=slug, token=request.token
        )
    except ValueError:
        raise NotPermitted("Invalid token")
    if result is None:
        raise ResourceNotFound("Channel not found")
    return result
