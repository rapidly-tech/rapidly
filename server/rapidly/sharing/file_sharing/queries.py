"""Channel and secret storage repository using Redis."""

import base64
import functools
import hashlib
import hmac
import json
import uuid
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

import structlog
from cryptography.fernet import Fernet

from rapidly.config import settings
from rapidly.redis import Redis

from .redis_scripts import (
    ATOMIC_DESTROY_CHANNEL_LUA,
    ATOMIC_DOWNLOAD_INCR_LUA,
    ATOMIC_INCR_EXPIRE_LUA,
    ATOMIC_PENDING_DESTRUCTION_LUA,
)
from .slugs import (
    SLUG_MAX_ATTEMPTS,
    generate_long_slug,
    generate_secret,
    generate_short_slug,
)

_log = structlog.get_logger(__name__)


@functools.cache
def _fernet() -> Fernet:
    """Fernet instance for encrypting tokens at rest, keyed from the app secret."""
    digest = hashlib.sha256(settings.SECRET.encode()).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def _encrypt_token(token: str) -> str:
    """Encrypt a token for safe storage in Redis."""
    return _fernet().encrypt(token.encode()).decode()


def _decrypt_token(encrypted: str | bytes) -> str:
    """Decrypt a token retrieved from Redis."""
    raw = encrypted if isinstance(encrypted, bytes) else encrypted.encode()
    return _fernet().decrypt(raw).decode()


def _hash_secret(raw_secret: str) -> str:
    """Hash a channel secret for safe storage in Redis.

    Uses keyed BLAKE2b (via get_token_hash) so the raw secret is never
    persisted. Consistent with all other token storage in the application.
    """
    from rapidly.core.crypto import get_token_hash

    return get_token_hash(raw_secret, secret=settings.SECRET)


# ── Constants ──

# Delay before channel destruction takes effect (in seconds)
# This gives uploaders time to detect abuse and cancel the destruction
CHANNEL_DESTRUCTION_DELAY = 30

# Registry of supported session kinds. Extended by each chamber. Kept as
# a single source of truth so validation at call sites can fail closed on
# typos or malicious input.
#   "file"   — file sharing (Phase A).
#   "screen" — Screen chamber (Phase B, PR 5).
SESSION_KINDS: set[str] = {"file", "screen"}


def validate_session_kind(kind: str) -> None:
    """Raise ``ValueError`` if ``kind`` is not a registered session kind.

    Deliberately NOT called from ``ChannelData.from_dict`` — that method must
    always succeed on any payload we previously wrote to Redis. Validation
    belongs at construction sites (API handlers, actions) so unknown kinds
    are rejected at the boundary, not when reading storage.
    """
    if kind not in SESSION_KINDS:
        raise ValueError(
            f"Unknown session_kind {kind!r} (valid: {sorted(SESSION_KINDS)})"
        )


# ── Data Structures ──


@dataclass
class SecretData:
    """Internal secret data structure."""

    message: str
    price_cents: int | None = None
    currency: str = "usd"
    title: str | None = None
    workspace_id: str | None = None
    seller_stripe_id: str | None = None

    @property
    def is_paid(self) -> bool:
        return self.price_cents is not None and self.price_cents > 0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SecretData":
        return cls(
            message=data["message"],
            price_cents=data.get("price_cents"),
            currency=data.get("currency", "usd"),
            title=data.get("title"),
            workspace_id=data.get("workspace_id"),
            seller_stripe_id=data.get("seller_stripe_id"),
        )


@dataclass
class ChannelData:
    """Internal channel data structure."""

    secret: str
    long_slug: str
    short_slug: str
    max_downloads: int = 0  # 0 = unlimited
    price_cents: int | None = None
    currency: str = "usd"
    seller_stripe_id: str | None = None
    seller_account_id: str | None = None
    user_id: str | None = None
    title: str | None = None
    file_name: str | None = None
    file_size_bytes: int | None = None
    share_id: str | None = None
    creator_country: str = ""
    creator_continent: str = ""
    # Kind of P2P session this channel hosts. Defaults to "file" so every
    # pre-existing Redis entry and every current create_channel call continues
    # to behave identically. Future chambers (screen, watch, ...) register new
    # values in SESSION_KINDS.
    session_kind: str = "file"
    # Screen-chamber fields (session_kind="screen"). Optional at the storage
    # layer so file-sharing rows continue to round-trip unchanged.
    max_viewers: int = 0  # 0 = unlimited; screen API caps at 10 in v1.
    screen_started_at: str | None = None  # ISO-8601, informational only.

    @property
    def is_paid(self) -> bool:
        return self.price_cents is not None and self.price_cents > 0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ChannelData":
        return cls(
            secret=data["secret"],
            long_slug=data["long_slug"],
            short_slug=data["short_slug"],
            max_downloads=data.get("max_downloads", 0),
            price_cents=data.get("price_cents"),
            currency=data.get("currency", "usd"),
            seller_stripe_id=data.get("seller_stripe_id"),
            seller_account_id=data.get("seller_account_id"),
            user_id=data.get("user_id"),
            title=data.get("title"),
            file_name=data.get("file_name"),
            file_size_bytes=data.get("file_size_bytes"),
            share_id=data.get("share_id"),
            creator_country=data.get("creator_country", ""),
            creator_continent=data.get("creator_continent", ""),
            # Backward-compatible: entries written before session_kind existed
            # read back as "file". No migration required.
            session_kind=data.get("session_kind", "file"),
            # Screen-chamber fields default to their "absent" values so every
            # pre-existing file-sharing row continues to round-trip intact.
            max_viewers=data.get("max_viewers", 0),
            screen_started_at=data.get("screen_started_at"),
        )


class ChannelRepository:
    """Redis-backed channel storage."""

    def __init__(self, redis: Redis):
        self._redis = redis

    # ── Key Helpers ──

    def _key(self, slug: str) -> str:
        return f"file-sharing:channel:{slug}"

    def _reader_token_key(self, slug: str) -> str:
        """Key for storing hashed reader authorization token."""
        return f"file-sharing:channel:reader_token:{slug}"

    def _pending_token_key(self, slug: str) -> str:
        """Key for blocking access until reader token is registered."""
        return f"file-sharing:channel:pending_token:{slug}"

    def _pending_destruction_key(self, slug: str) -> str:
        """Key for tracking pending destruction requests."""
        return f"file-sharing:channel:pending_destruction:{slug}"

    def _payment_token_key(self, slug: str) -> str:
        """Key for storing hashed payment tokens (SET of SHA256 hashes)."""
        return f"file-sharing:channel:payment_tokens:{slug}"

    # ── Channel Lifecycle ──

    async def _generate_unique_slugs(self) -> tuple[str, str]:
        """Generate unique short and long slugs with atomic reservation.

        Uses SET NX (set-if-not-exists) to atomically reserve slugs,
        preventing TOCTOU races where concurrent requests could claim
        the same slug between the existence check and the actual store.
        Reservations have a short TTL and are overwritten by create_channel.
        """
        # Generate short slug with atomic reservation
        short_slug = None
        short_collisions = 0
        for _ in range(SLUG_MAX_ATTEMPTS):
            candidate = generate_short_slug()
            # Atomically reserve with a short TTL (overwritten by create_channel)
            reserved = await self._redis.set(
                self._key(candidate), "__reserved__", nx=True, ex=30
            )
            if reserved:
                short_slug = candidate
                break
            short_collisions += 1
        if short_slug is None:
            raise RuntimeError(
                "Failed to generate unique short slug after max attempts"
            )
        if short_collisions > 0:
            _log.warning(
                "Short slug collision(s) during generation",
                extra={
                    "event": "slug_collision",
                    "slug_type": "short",
                    "collisions": short_collisions,
                    "max_attempts": SLUG_MAX_ATTEMPTS,
                },
            )

        # Generate long slug with atomic reservation
        long_slug = None
        long_collisions = 0
        for _ in range(SLUG_MAX_ATTEMPTS):
            candidate = generate_long_slug()
            reserved = await self._redis.set(
                self._key(candidate), "__reserved__", nx=True, ex=30
            )
            if reserved:
                long_slug = candidate
                break
            long_collisions += 1
        if long_slug is None:
            # Clean up short slug reservation on failure
            await self._redis.delete(self._key(short_slug))
            raise RuntimeError("Failed to generate unique long slug after max attempts")
        if long_collisions > 0:
            _log.warning(
                "Long slug collision(s) during generation",
                extra={
                    "event": "slug_collision",
                    "slug_type": "long",
                    "collisions": long_collisions,
                    "max_attempts": SLUG_MAX_ATTEMPTS,
                },
            )

        return short_slug, long_slug

    async def create_channel(
        self,
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
        share_id: str | None = None,
        creator_country: str = "",
        creator_continent: str = "",
    ) -> tuple[ChannelData, str]:
        """Create a new channel with unique slugs.

        Returns (channel_data, raw_secret) — the raw secret is returned only
        at creation time and never stored; Redis holds its SHA-256 hash.
        """
        # Use longer TTL for paid channels
        if ttl is None:
            if price_cents is not None and price_cents > 0:
                ttl = settings.FILE_SHARING_PAID_CHANNEL_TTL
            else:
                ttl = settings.FILE_SHARING_CHANNEL_TTL
        short_slug, long_slug = await self._generate_unique_slugs()

        raw_secret = generate_secret()
        channel = ChannelData(
            secret=_hash_secret(raw_secret),
            long_slug=long_slug,
            short_slug=short_slug,
            max_downloads=max_downloads,
            price_cents=price_cents,
            currency=currency,
            seller_stripe_id=seller_stripe_id,
            seller_account_id=seller_account_id,
            user_id=user_id,
            title=title,
            file_name=file_name,
            file_size_bytes=file_size_bytes,
            share_id=share_id,
            creator_country=creator_country,
            creator_continent=creator_continent,
        )

        # Store channel data as JSON
        channel_json = json.dumps(channel.to_dict())

        # Atomic pipeline: store both slugs + pending tokens in one round-trip
        # Prevents inconsistent state if connection drops between operations
        async with self._redis.pipeline(transaction=True) as pipe:
            pipe.setex(self._key(short_slug), ttl, channel_json)
            pipe.setex(self._key(long_slug), ttl, channel_json)
            # Block access until reader token is registered (120s timeout as safety net)
            pending_ttl = 120
            pipe.setex(self._pending_token_key(short_slug), pending_ttl, "1")
            pipe.setex(self._pending_token_key(long_slug), pending_ttl, "1")
            await pipe.execute()

        return channel, raw_secret

    async def fetch_channel(self, slug: str) -> ChannelData | None:
        """Fetch a channel by either short or long slug."""
        data = await self._redis.get(self._key(slug))
        if data is None:
            return None
        try:
            return ChannelData.from_dict(json.loads(data))
        except (json.JSONDecodeError, KeyError):
            # Slug exists but contains non-JSON data (e.g. "__reserved__" sentinel
            # from concurrent slug reservation) or has an unexpected schema.
            return None

    async def renew_channel(
        self, slug: str, secret: str, ttl: int | None = None
    ) -> bool:
        """Renew a channel's TTL if the secret matches.

        Also cancels any pending destruction request, as renewal proves
        the legitimate owner is still active.

        Note: Secret verification uses hmac.compare_digest for constant-time
        comparison (timing-attack resistance). This is not atomic with the
        subsequent EXPIRE pipeline, but the race window is negligible
        (only the uploader has the secret) and moving to Lua would lose
        the constant-time comparison guarantee.
        """
        channel = await self.fetch_channel(slug)
        if channel is None or not hmac.compare_digest(
            channel.secret, _hash_secret(secret)
        ):
            return False

        ttl = ttl or settings.FILE_SHARING_CHANNEL_TTL

        # Check reader token existence before pipeline — if expired, log a warning.
        # EXPIRE is a no-op on non-existent keys, so the channel would outlive
        # its reader token, leaving downloaders unable to authenticate.
        reader_token_key = self._reader_token_key(channel.short_slug)
        reader_token_exists = await self._redis.exists(reader_token_key) > 0

        # Atomic pipeline: refresh TTL for both slugs + ancillary keys in one round-trip
        async with self._redis.pipeline(transaction=True) as pipe:
            pipe.expire(self._key(channel.short_slug), ttl)
            pipe.expire(self._key(channel.long_slug), ttl)
            # Renew reader token key (prevents auth bypass when channel outlives token TTL)
            if reader_token_exists:
                pipe.expire(reader_token_key, ttl)
            # Renew download count key so it doesn't expire before the channel
            pipe.expire(self._download_count_key(channel.short_slug), ttl)
            # Cancel any pending destruction atomically with the renewal
            pipe.delete(self._pending_destruction_key(channel.short_slug))
            await pipe.execute()

        if not reader_token_exists:
            _log.warning(
                "Reader token expired before channel renewal",
                extra={
                    "event": "reader_token_expired_on_renew",
                    "short_slug": channel.short_slug,
                },
            )

        return True

    async def request_channel_destruction(
        self, slug: str, secret: str
    ) -> tuple[bool, bool, str]:
        """Request authenticated channel destruction with a delay.

        Returns:
            tuple[bool, bool, str]: (success, is_immediate, message)
            - success: True if the request was authenticated and processed
            - is_immediate: True if destruction happened immediately (second request)
            - message: Description of what happened

        Security: Requires the channel ownership secret. Uses atomic Lua scripts
        to prevent TOCTOU races between secret verification and state changes.
        Implements a two-phase destruction with a delay to prevent accidental
        immediate deletion.
        """
        # We need the channel data to build Redis keys, but the Lua script
        # re-verifies the secret atomically at execution time.
        channel = await self.fetch_channel(slug)
        if channel is None:
            return (False, False, "Channel not found")

        # Hash the incoming secret to compare against the stored hash.
        # Constant-time comparison in Python before calling Lua
        # (Lua string comparison is not constant-time, so this eliminates
        # timing side-channel at zero cost — Lua re-verifies atomically).
        secret_hash = _hash_secret(secret)
        if not hmac.compare_digest(channel.secret, secret_hash):
            return (False, False, "Invalid secret")

        pending_key = self._pending_destruction_key(channel.short_slug)
        channel_key = self._key(channel.short_slug)

        # First, try atomic pending-destruction (checks secret hash + pending atomically)
        destruction_info = json.dumps(
            {
                "requested_at": datetime.now(UTC).isoformat(),
                "short_slug": channel.short_slug,
                "long_slug": channel.long_slug,
            }
        )
        result = await self._redis.eval(
            ATOMIC_PENDING_DESTRUCTION_LUA,
            2,
            channel_key,
            pending_key,
            CHANNEL_DESTRUCTION_DELAY,
            destruction_info,
        )

        if result == 0:
            return (False, False, "Channel not found")
        if result == 1:
            # First request - pending destruction set
            _log.info(
                "Channel destruction requested",
                extra={
                    "event": "channel_destruction_requested",
                    "short_slug": channel.short_slug,
                    "long_slug": channel.long_slug,
                    "max_downloads": channel.max_downloads,
                    "delay_seconds": CHANNEL_DESTRUCTION_DELAY,
                    "timestamp": datetime.now(UTC).isoformat(),
                },
            )
            return (
                True,
                False,
                f"Destruction pending. Channel will be destroyed in {CHANNEL_DESTRUCTION_DELAY} seconds "
                "unless cancelled by the owner. Request again to confirm immediately.",
            )

        # result == 2: already pending — confirm destruction atomically
        all_keys = [
            channel_key,
            pending_key,
            self._key(channel.long_slug),
            self._reader_token_key(channel.short_slug),
            self._reader_token_key(channel.long_slug),
            self._pending_token_key(channel.short_slug),
            self._pending_token_key(channel.long_slug),
            self._pw_attempts_key(channel.short_slug),
            self._download_count_key(channel.short_slug),
        ]
        destroy_result = await self._redis.eval(
            ATOMIC_DESTROY_CHANNEL_LUA,
            len(all_keys),
            *all_keys,
        )

        if destroy_result == 1:
            _log.warning(
                "Channel destruction confirmed",
                extra={
                    "event": "channel_destruction_confirmed",
                    "short_slug": channel.short_slug,
                    "long_slug": channel.long_slug,
                    "max_downloads": channel.max_downloads,
                    "timestamp": datetime.now(UTC).isoformat(),
                },
            )
            return (True, True, "Channel destroyed")

        # Edge case: channel changed between the two Lua calls
        if destroy_result == 0:
            return (False, False, "Channel not found")
        if destroy_result == -1:
            return (False, False, "Invalid secret")
        # -2: pending key expired between the two calls
        return (False, False, "Destruction confirmation expired. Please try again.")

    # ── Reader Token Management ──

    async def is_pending_token(
        self, slug: str, *, channel: ChannelData | None = None
    ) -> bool:
        """Check if a pending token marker exists for the given slug."""
        if channel is None:
            channel = await self.fetch_channel(slug)
        if channel is None:
            return False
        pending = await self._redis.get(self._pending_token_key(channel.short_slug))
        return pending is not None

    async def has_reader_token(
        self, slug: str, *, channel: ChannelData | None = None
    ) -> bool:
        """Check if a reader token is stored for the given slug."""
        if channel is None:
            channel = await self.fetch_channel(slug)
        if channel is None:
            return False
        stored = await self._redis.get(self._reader_token_key(channel.short_slug))
        return stored is not None

    async def set_reader_token(self, slug: str, secret: str, token_hash: str) -> bool:
        """Store a hashed reader token for a channel.

        The reader token prevents slug enumeration — downloaders must
        prove they have the full URL (with encryption key) to fetch channel info.
        Requires channel secret to prove caller is the uploader.
        """
        channel = await self.fetch_channel(slug)
        if channel is None or not hmac.compare_digest(
            channel.secret, _hash_secret(secret)
        ):
            return False

        ttl = await self._redis.ttl(self._key(channel.short_slug))
        if ttl <= 0:
            return False

        # Normalize to lowercase — validate_reader_token() compares against
        # hexdigest() which always returns lowercase hex.
        token_hash = token_hash.lower()

        # Atomic pipeline: store token + clear pending markers in one round-trip
        # Only store under short_slug — lookups always use short_slug via channel data
        async with self._redis.pipeline(transaction=True) as pipe:
            pipe.setex(self._reader_token_key(channel.short_slug), ttl, token_hash)
            # Clear pending-token marker — channel is now fully protected
            pipe.delete(self._pending_token_key(channel.short_slug))
            pipe.delete(self._pending_token_key(channel.long_slug))
            await pipe.execute()

        return True

    async def validate_reader_token(
        self, slug: str, token: str, *, channel: ChannelData | None = None
    ) -> bool:
        """Validate a reader token against the stored hash.

        Returns False if no token is stored (the token key may have expired
        while the channel is still alive — callers should treat this as
        unauthorized rather than silently allowing access).

        Pass a pre-fetched ``channel`` to avoid a redundant Redis GET.
        """
        if channel is None:
            channel = await self.fetch_channel(slug)
        if channel is None:
            return False

        stored_hash_raw = await self._redis.get(
            self._reader_token_key(channel.short_slug)
        )
        if stored_hash_raw is None:
            # Token key expired (TTL drift) — deny access to prevent bypass
            return False

        # Decode bytes to str if needed (FakeRedis returns bytes, real Redis returns str)
        stored_hash = (
            stored_hash_raw.decode()
            if isinstance(stored_hash_raw, bytes)
            else stored_hash_raw
        )
        # Hash the provided token and compare (constant-time)
        incoming_hash = hashlib.sha256(token.encode()).hexdigest()
        return hmac.compare_digest(incoming_hash, stored_hash)

    # ── Password Attempt Tracking ──

    MAX_PASSWORD_ATTEMPTS = 10
    PASSWORD_ATTEMPT_TTL = 900  # 15 minutes

    def _pw_attempts_key(self, slug: str) -> str:
        """Redis key for tracking password attempts per channel."""
        return f"file-sharing:channel:pw_attempts:{slug}"

    async def record_password_attempt(self, slug: str, secret: str) -> bool:
        """Atomically increment attempt counter.

        Returns True if the attempt is within the rate limit.
        Requires the channel secret to prove caller is the uploader.
        """
        channel = await self.fetch_channel(slug)
        if channel is None or not hmac.compare_digest(
            channel.secret, _hash_secret(secret)
        ):
            return False

        key = self._pw_attempts_key(channel.short_slug)
        # Atomic INCR + EXPIRE via Lua to prevent orphaned keys on crash
        current = await self._redis.eval(
            ATOMIC_INCR_EXPIRE_LUA,
            1,
            key,
            self.PASSWORD_ATTEMPT_TTL,
        )

        allowed = current <= self.MAX_PASSWORD_ATTEMPTS

        if not allowed:
            _log.warning(
                "Password attempts exhausted for channel",
                extra={
                    "event": "password_attempts_exhausted",
                    "short_slug": channel.short_slug,
                    "attempts": current,
                    "timestamp": datetime.now(UTC).isoformat(),
                },
            )

        return allowed

    # ── Download Tracking ──

    def _download_count_key(self, slug: str) -> str:
        """Redis key for tracking completed downloads per channel."""
        return f"file-sharing:channel:download_count:{slug}"

    async def check_download_available(
        self, slug: str, *, channel: ChannelData | None = None
    ) -> bool:
        """Read-only check whether downloads remain for a channel.

        Does NOT increment the counter — this is a non-destructive check
        used when a downloader fetches channel info. The actual slot claiming
        happens in record_download_complete() on download completion.

        This prevents wasted slots from page reloads, failed WebRTC
        connections, or users who view info but don't download.

        Returns True if unlimited (max_downloads == 0) or slots remain.
        Pass a pre-fetched ``channel`` to avoid a redundant Redis GET.
        """
        if channel is None:
            channel = await self.fetch_channel(slug)
        if channel is None:
            return False

        # Unlimited
        if channel.max_downloads == 0:
            return True

        key = self._download_count_key(channel.short_slug)
        count_str = await self._redis.get(key)
        current = int(count_str) if count_str else 0

        if current >= channel.max_downloads:
            _log.info(
                "Download limit reached for channel (check)",
                extra={
                    "event": "download_limit_reached",
                    "short_slug": channel.short_slug,
                    "max_downloads": channel.max_downloads,
                    "current": current,
                    "timestamp": datetime.now(UTC).isoformat(),
                },
            )
            return False

        return True

    async def record_download_complete(
        self, slug: str, reader_token: str
    ) -> tuple[bool, int, int]:
        """Atomically claim a download slot on completed download.

        This is the primary download-limit enforcement point. Called when
        the downloader confirms successful receipt of all files.

        Returns (success, remaining, download_count) where remaining is the
        number of downloads left (-1 = unlimited) and download_count is the
        1-based slot number of this download. Requires valid reader token.
        """
        # Fetch channel once and reuse for all checks
        channel = await self.fetch_channel(slug)
        if channel is None:
            return (False, 0, 0)

        # Block during pending-token window (channel just created, reader token not yet set)
        if await self.is_pending_token(slug, channel=channel):
            return (False, 0, 0)

        # Validate reader token (reuse shared method with pre-fetched channel)
        if not await self.validate_reader_token(slug, reader_token, channel=channel):
            return (False, 0, 0)

        key = self._download_count_key(channel.short_slug)
        ttl = await self._redis.ttl(self._key(channel.short_slug))
        counter_ttl = max(ttl, 3600)

        # Unlimited — still track count for metrics but always allow
        if channel.max_downloads == 0:
            download_count = await self._redis.incr(key)
            if download_count == 1:
                await self._redis.expire(key, counter_ttl)
            return (True, -1, int(download_count))

        # Atomic check-and-increment: only increments if count < max_downloads,
        # preventing TOCTOU race where concurrent requests could exceed the limit.
        result = await self._redis.eval(
            ATOMIC_DOWNLOAD_INCR_LUA,
            1,
            key,
            channel.max_downloads,
            counter_ttl,
        )

        if int(result) == -1:
            _log.info(
                "Download limit reached for channel",
                extra={
                    "event": "download_limit_reached",
                    "short_slug": channel.short_slug,
                    "max_downloads": channel.max_downloads,
                    "timestamp": datetime.now(UTC).isoformat(),
                },
            )
            return (False, 0, 0)

        download_count = int(result)
        remaining = max(0, channel.max_downloads - download_count)
        return (True, remaining, download_count)

    async def delete_channel(self, channel: ChannelData) -> None:
        """Delete a channel and all associated keys from Redis.

        Used by the report flow to prevent the uploader from reconnecting
        after a channel is reported for abuse.
        """
        keys = [
            self._key(channel.short_slug),
            self._key(channel.long_slug),
            self._reader_token_key(channel.short_slug),
            self._reader_token_key(channel.long_slug),
            self._pending_token_key(channel.short_slug),
            self._pending_token_key(channel.long_slug),
            self._pw_attempts_key(channel.short_slug),
            self._download_count_key(channel.short_slug),
            self._pending_destruction_key(channel.short_slug),
            self._payment_token_key(channel.short_slug),
        ]
        await self._redis.delete(*keys)

    # ── Checksum Storage ──

    def _checksums_key(self, slug: str) -> str:
        """Redis key for storing file checksums per channel."""
        return f"file-sharing:channel:{slug}:checksums"

    async def store_checksums(
        self, slug: str, secret: str, checksums: dict[str, str]
    ) -> bool:
        """Store SHA-256 checksums for a channel's files.

        Requires channel secret. Stored with same TTL as the channel.
        """
        channel = await self.fetch_channel(slug)
        if channel is None or not hmac.compare_digest(
            channel.secret, _hash_secret(secret)
        ):
            return False

        ttl = await self._redis.ttl(self._key(channel.short_slug))
        if ttl <= 0:
            return False

        checksums_json = json.dumps(checksums)
        await self._redis.setex(
            self._checksums_key(channel.short_slug), ttl, checksums_json
        )
        return True

    async def fetch_checksums(
        self, slug: str, reader_token: str
    ) -> dict[str, str] | None:
        """Fetch checksums for a channel. Requires valid reader token."""
        channel = await self.fetch_channel(slug)
        if channel is None:
            return None

        # Validate reader token (reuse shared method with pre-fetched channel)
        if not await self.validate_reader_token(slug, reader_token, channel=channel):
            return None

        data = await self._redis.get(self._checksums_key(channel.short_slug))
        if data is None:
            return None
        try:
            return json.loads(data)
        except (json.JSONDecodeError, TypeError):
            return None

    # ── Payment Tokens ──

    async def store_payment_token(
        self,
        slug: str,
        token_hash: str,
        ttl: int,
        *,
        buyer_fingerprint: str = "",
    ) -> None:
        """Store a SHA256 hash of a payment token bound to buyer fingerprint.

        The stored value is ``token_hash:buyer_fingerprint`` so that
        validation can verify both the token and the buyer's identity,
        preventing token reuse by a different party.
        """
        value = f"{token_hash}:{buyer_fingerprint}"
        key = self._payment_token_key(slug)
        async with self._redis.pipeline(transaction=True) as pipe:
            pipe.sadd(key, value)
            pipe.expire(key, ttl)
            await pipe.execute()

    async def validate_payment_token(
        self,
        slug: str,
        token: str,
        *,
        channel: ChannelData | None = None,
        buyer_fingerprint: str = "",
    ) -> bool:
        """Check if a buyer has a valid payment token via SISMEMBER.

        Verifies both the token hash and the buyer fingerprint to prevent
        token reuse if the success URL is shared or intercepted.
        """
        if channel is None:
            channel = await self.fetch_channel(slug)
        if channel is None:
            return False
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        # Verify both token hash and buyer fingerprint binding
        bound_value = f"{token_hash}:{buyer_fingerprint}"
        return bool(
            await self._redis.sismember(
                self._payment_token_key(channel.short_slug), bound_value
            )
        )

    # ── Checkout Session → Payment Token Exchange ──

    _CHECKOUT_TOKEN_TTL = 900  # 15 minutes — enough for Stripe redirect

    def _checkout_token_key(self, slug: str, checkout_session_id: str) -> str:
        return f"file-sharing:checkout-token:{slug}:{checkout_session_id}"

    async def store_checkout_payment_token(
        self,
        slug: str,
        checkout_session_id: str,
        payment_token: str,
    ) -> None:
        """Store a payment token keyed by slug + Stripe checkout session ID.

        This allows the frontend to claim the token via an API call after
        the Stripe redirect, instead of exposing it in the URL.
        The mapping is one-time-use and expires after 15 minutes.
        The token is encrypted at rest to avoid clear-text storage.
        """
        key = self._checkout_token_key(slug, checkout_session_id)
        await self._redis.setex(
            key, self._CHECKOUT_TOKEN_TTL, _encrypt_token(payment_token)
        )

    async def claim_checkout_payment_token(
        self, slug: str, checkout_session_id: str
    ) -> str | None:
        """Atomically retrieve and delete the payment token for a checkout session.

        Returns the decrypted token if found, None otherwise. One-time use —
        the key is deleted after retrieval to prevent replay.
        """
        key = self._checkout_token_key(slug, checkout_session_id)
        # GETDEL is atomic — prevents race conditions
        encrypted: str | None = await self._redis.getdel(key)
        if encrypted is None:
            return None
        return _decrypt_token(encrypted)


# ── Secret Repository ──


class SecretRepository:
    """Redis-backed secret storage."""

    _PREFIXES = {"secret": "file-sharing:secret", "file": "file-sharing:file"}

    def __init__(self, redis: Redis):
        self._redis = redis

    def _key(self, kind: str, item_id: str) -> str:
        return f"{self._PREFIXES[kind]}:{item_id}"

    async def _create(
        self,
        kind: str,
        message: str,
        expiration: int,
        *,
        price_cents: int | None = None,
        currency: str = "usd",
        title: str | None = None,
        workspace_id: str | None = None,
        seller_stripe_id: str | None = None,
    ) -> str:
        """Create a one-time secret/file. Deleted on first fetch."""
        item_id = str(uuid.uuid4())
        secret_json = json.dumps(
            SecretData(
                message=message,
                price_cents=price_cents,
                currency=currency,
                title=title,
                workspace_id=workspace_id,
                seller_stripe_id=seller_stripe_id,
            ).to_dict()
        )
        await self._redis.setex(self._key(kind, item_id), expiration, secret_json)
        return item_id

    async def _fetch(self, kind: str, item_id: str) -> SecretData | None:
        """Fetch and atomically delete a one-time secret/file."""
        data = await self._redis.getdel(self._key(kind, item_id))
        if data is None:
            return None
        return SecretData.from_dict(json.loads(data))

    async def _peek(self, kind: str, item_id: str) -> SecretData | None:
        """Read secret metadata without consuming it (no deletion)."""
        data = await self._redis.get(self._key(kind, item_id))
        if data is None:
            return None
        return SecretData.from_dict(json.loads(data))

    # ── Paid Secret Index ──

    _PAID_SECRETS_PREFIX = "file-sharing:paid-secrets"

    def _paid_secrets_key(self, workspace_id: str) -> str:
        return f"{self._PAID_SECRETS_PREFIX}:{workspace_id}"

    async def index_paid_secret(
        self,
        workspace_id: str,
        item_id: str,
        *,
        title: str | None,
        price_cents: int,
        currency: str,
        expiration: int,
    ) -> None:
        """Add a paid secret to the workspace's storefront index (HASH keyed by UUID)."""
        now = datetime.now(UTC)
        entry = json.dumps(
            {
                "id": item_id,
                "uuid": item_id,
                "title": title,
                "price_cents": price_cents,
                "currency": currency,
                "created_at": now.isoformat(),
                "expires_at": (now + timedelta(seconds=expiration)).isoformat(),
            }
        )
        key = self._paid_secrets_key(workspace_id)
        # Read TTL before entering the transaction
        current_ttl = await self._redis.ttl(key)
        async with self._redis.pipeline(transaction=True) as pipe:
            pipe.hset(key, item_id, entry)
            # Extend TTL to cover the longest-lived secret
            if current_ttl < expiration:
                pipe.expire(key, expiration)
            await pipe.execute()

    async def list_paid_secrets(self, workspace_id: str) -> list[dict[str, Any]]:
        """List all paid secrets for a workspace's storefront."""
        key = self._paid_secrets_key(workspace_id)
        entries = await self._redis.hgetall(key)
        if not entries:
            return []

        # Batch-check existence of all secrets in one pipeline call
        item_ids = list(entries.keys())
        async with self._redis.pipeline() as pipe:
            for item_id in item_ids:
                pipe.exists(self._key("secret", item_id))
            exists_results = await pipe.execute()

        result = []
        stale_keys: list[str] = []
        for item_id, exists in zip(item_ids, exists_results):
            if exists:
                result.append(json.loads(entries[item_id]))
            else:
                stale_keys.append(item_id)
        # Clean up expired entries
        if stale_keys:
            await self._redis.hdel(key, *stale_keys)
        return result

    # ── Stats ──

    _STATS_KEY = "file-sharing:stats:secrets_created"

    _STATS_CACHE_KEY = "file-sharing:stats:cached_total"

    async def increment_created_count(self, workspace_id: str | None = None) -> None:
        """Increment the persistent counter of secrets/files created."""
        await self._redis.incr(self._STATS_KEY)
        # Invalidate the cached stats so the counter updates immediately
        await self._redis.delete(self._STATS_CACHE_KEY)
        if workspace_id:
            await self._redis.incr(f"file-sharing:stats:secrets_created:{workspace_id}")

    async def get_created_count(self) -> int:
        """Return the total number of secrets/files ever created."""
        val = await self._redis.get(self._STATS_KEY)
        return int(val) if val else 0

    async def get_workspace_created_count(self, workspace_id: str) -> int:
        """Return the number of secrets/files created for a workspace."""
        val = await self._redis.get(
            f"file-sharing:stats:secrets_created:{workspace_id}"
        )
        return int(val) if val else 0

    # Public convenience methods (preserve existing API)
    async def create_secret(
        self,
        message: str,
        expiration: int,
        workspace_id: str | None = None,
        *,
        price_cents: int | None = None,
        currency: str = "usd",
        title: str | None = None,
        seller_stripe_id: str | None = None,
    ) -> str:
        item_id = await self._create(
            "secret",
            message,
            expiration,
            price_cents=price_cents,
            currency=currency,
            title=title,
            workspace_id=workspace_id,
            seller_stripe_id=seller_stripe_id,
        )
        await self.increment_created_count(workspace_id)
        # Index paid secrets for storefront listing
        if price_cents and price_cents > 0 and workspace_id:
            await self.index_paid_secret(
                workspace_id,
                item_id,
                title=title,
                price_cents=price_cents,
                currency=currency,
                expiration=expiration,
            )
        return item_id

    async def create_file(
        self,
        message: str,
        expiration: int,
        workspace_id: str | None = None,
        *,
        price_cents: int | None = None,
        currency: str = "usd",
        title: str | None = None,
        seller_stripe_id: str | None = None,
    ) -> str:
        item_id = await self._create(
            "file",
            message,
            expiration,
            price_cents=price_cents,
            currency=currency,
            title=title,
            workspace_id=workspace_id,
            seller_stripe_id=seller_stripe_id,
        )
        await self.increment_created_count(workspace_id)
        if price_cents and price_cents > 0 and workspace_id:
            await self.index_paid_secret(
                workspace_id,
                item_id,
                title=title,
                price_cents=price_cents,
                currency=currency,
                expiration=expiration,
            )
        return item_id

    async def fetch_secret(self, secret_id: str) -> SecretData | None:
        return await self._fetch("secret", secret_id)

    async def fetch_file(self, file_id: str) -> SecretData | None:
        return await self._fetch("file", file_id)

    async def peek_secret(self, secret_id: str) -> SecretData | None:
        """Read secret metadata without consuming it."""
        return await self._peek("secret", secret_id)

    async def peek_file(self, file_id: str) -> SecretData | None:
        """Read file secret metadata without consuming it."""
        return await self._peek("file", file_id)

    # ── Secret Payment Tokens ──

    _SECRET_PAYMENT_TOKEN_PREFIX = "file-sharing:secret:payment_tokens"
    _SECRET_CHECKOUT_TOKEN_PREFIX = "file-sharing:secret:checkout-token"
    _SECRET_CHECKOUT_TOKEN_TTL = 900  # 15 minutes

    def _secret_payment_token_key(self, secret_id: str) -> str:
        return f"{self._SECRET_PAYMENT_TOKEN_PREFIX}:{secret_id}"

    def _secret_checkout_token_key(
        self, secret_id: str, checkout_session_id: str
    ) -> str:
        return f"{self._SECRET_CHECKOUT_TOKEN_PREFIX}:{secret_id}:{checkout_session_id}"

    async def store_secret_payment_token(
        self,
        secret_id: str,
        token_hash: str,
        ttl: int,
        *,
        buyer_fingerprint: str = "",
    ) -> None:
        """Store a payment token hash for a paid secret (atomic)."""
        bound_value = f"{token_hash}:{buyer_fingerprint}"
        key = self._secret_payment_token_key(secret_id)
        async with self._redis.pipeline(transaction=True) as pipe:
            pipe.sadd(key, bound_value)
            pipe.expire(key, ttl)
            await pipe.execute()

    async def validate_secret_payment_token(
        self,
        secret_id: str,
        token: str,
        *,
        buyer_fingerprint: str = "",
    ) -> bool:
        """Check if a buyer has a valid payment token for a secret."""
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        bound_value = f"{token_hash}:{buyer_fingerprint}"
        return bool(
            await self._redis.sismember(
                self._secret_payment_token_key(secret_id), bound_value
            )
        )

    async def store_secret_checkout_payment_token(
        self,
        secret_id: str,
        checkout_session_id: str,
        payment_token: str,
    ) -> None:
        """Store a payment token keyed by secret_id + Stripe checkout session ID.

        The token is encrypted at rest to avoid clear-text storage.
        """
        key = self._secret_checkout_token_key(secret_id, checkout_session_id)
        await self._redis.setex(
            key, self._SECRET_CHECKOUT_TOKEN_TTL, _encrypt_token(payment_token)
        )

    async def claim_secret_checkout_payment_token(
        self, secret_id: str, checkout_session_id: str
    ) -> str | None:
        """Atomically retrieve and delete the payment token for a checkout session."""
        key = self._secret_checkout_token_key(secret_id, checkout_session_id)
        encrypted: str | None = await self._redis.getdel(key)
        if encrypted is None:
            return None
        return _decrypt_token(encrypted)
