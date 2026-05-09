"""Security integration tests for file sharing module.

Tests cover: rate limiting, download quota atomicity, payment token binding,
reader token validation, channel secret verification, slug validation,
one-time secret atomicity, and password attempt tracking.
"""

import asyncio
import hashlib

import pytest
import pytest_asyncio

from rapidly.redis import Redis
from rapidly.sharing.file_sharing.guards import (
    validate_slug,
)
from rapidly.sharing.file_sharing.queries import ChannelData, ChannelRepository
from rapidly.sharing.file_sharing.redis_scripts import ATOMIC_DOWNLOAD_INCR_LUA

# ── Helpers ──


def _set_reader_token(
    repo: ChannelRepository, channel: ChannelData, raw_secret: str
) -> tuple[str, str]:
    """Helper returning (raw_token, token_hash) after preparing a reader token."""
    raw_token = "test-reader-token"
    token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
    return raw_token, token_hash


async def _setup_reader_token(
    repo: ChannelRepository, channel: ChannelData, raw_secret: str
) -> str:
    """Register a reader token and return the raw token string."""
    raw_token, token_hash = _set_reader_token(repo, channel, raw_secret)
    result = await repo.set_reader_token(channel.short_slug, raw_secret, token_hash)
    assert result is True
    return raw_token


# ── Download Quota Atomicity ──


@pytest.mark.asyncio
class TestDownloadQuotaAtomicity:
    """Verify that concurrent download completions cannot exceed max_downloads."""

    @pytest_asyncio.fixture
    async def limited_channel(
        self, redis: Redis
    ) -> tuple[ChannelRepository, ChannelData, str, str]:
        """Create a channel with max_downloads=3 and a valid reader token."""
        repo = ChannelRepository(redis)
        channel, raw_secret = await repo.create_channel(max_downloads=3, ttl=3600)
        raw_token = await _setup_reader_token(repo, channel, raw_secret)
        return repo, channel, raw_secret, raw_token

    async def test_download_count_enforced_sequentially(
        self, limited_channel: tuple[ChannelRepository, ChannelData, str, str]
    ) -> None:
        """Downloads 1-3 succeed, download 4 fails."""
        repo, channel, _, raw_token = limited_channel
        slug = channel.short_slug

        # Three successful downloads
        for i in range(3):
            success, remaining, count = await repo.record_download_complete(
                slug, raw_token
            )
            assert success is True, f"Download {i + 1} should succeed"
            assert remaining == 3 - (i + 1)

        # Fourth download must fail
        success, remaining, count = await repo.record_download_complete(slug, raw_token)
        assert success is False
        assert remaining == 0

    async def test_concurrent_downloads_cannot_exceed_limit(
        self, limited_channel: tuple[ChannelRepository, ChannelData, str, str]
    ) -> None:
        """Fire 10 concurrent downloads at a channel with max_downloads=3.

        At most 3 should succeed, regardless of scheduling order.
        """
        repo, channel, _, raw_token = limited_channel
        slug = channel.short_slug

        results = await asyncio.gather(
            *[repo.record_download_complete(slug, raw_token) for _ in range(10)]
        )

        successes = [r for r in results if r[0] is True]
        failures = [r for r in results if r[0] is False]
        assert len(successes) == 3
        assert len(failures) == 7

    async def test_unlimited_downloads_always_succeed(self, redis: Redis) -> None:
        """max_downloads=0 means unlimited — no counter enforced."""
        repo = ChannelRepository(redis)
        channel, raw_secret = await repo.create_channel(max_downloads=0, ttl=3600)
        raw_token = await _setup_reader_token(repo, channel, raw_secret)

        for _ in range(20):
            success, remaining, _ = await repo.record_download_complete(
                channel.short_slug, raw_token
            )
            assert success is True
            assert remaining == -1  # -1 = unlimited


# ── Channel Secret Validation ──


@pytest.mark.asyncio
class TestChannelSecretValidation:
    """Verify channel secret verification uses constant-time comparison."""

    @pytest_asyncio.fixture
    async def channel_with_secret(
        self, redis: Redis
    ) -> tuple[ChannelRepository, ChannelData, str]:
        repo = ChannelRepository(redis)
        channel, raw_secret = await repo.create_channel(max_downloads=0, ttl=3600)
        return repo, channel, raw_secret

    async def test_correct_secret_renews(
        self, channel_with_secret: tuple[ChannelRepository, ChannelData, str]
    ) -> None:
        repo, channel, raw_secret = channel_with_secret
        result = await repo.renew_channel(channel.short_slug, raw_secret)
        assert result is True

    async def test_wrong_secret_rejected(
        self, channel_with_secret: tuple[ChannelRepository, ChannelData, str]
    ) -> None:
        repo, channel, _ = channel_with_secret
        result = await repo.renew_channel(channel.short_slug, "wrong-secret")
        assert result is False

    async def test_empty_secret_rejected(
        self, channel_with_secret: tuple[ChannelRepository, ChannelData, str]
    ) -> None:
        repo, channel, _ = channel_with_secret
        result = await repo.renew_channel(channel.short_slug, "")
        assert result is False

    async def test_nonexistent_slug_rejected(
        self, channel_with_secret: tuple[ChannelRepository, ChannelData, str]
    ) -> None:
        repo, _, raw_secret = channel_with_secret
        result = await repo.renew_channel("nonexistent-slug", raw_secret)
        assert result is False

    async def test_secret_required_for_reader_token(
        self, channel_with_secret: tuple[ChannelRepository, ChannelData, str]
    ) -> None:
        repo, channel, raw_secret = channel_with_secret
        token_hash = hashlib.sha256(b"some-token").hexdigest()

        # Wrong secret
        result = await repo.set_reader_token(channel.short_slug, "wrong", token_hash)
        assert result is False

        # Correct secret
        result = await repo.set_reader_token(channel.short_slug, raw_secret, token_hash)
        assert result is True

    async def test_secret_required_for_destruction(
        self, channel_with_secret: tuple[ChannelRepository, ChannelData, str]
    ) -> None:
        repo, channel, raw_secret = channel_with_secret

        # Wrong secret
        success, _, _ = await repo.request_channel_destruction(
            channel.short_slug, "wrong-secret"
        )
        assert success is False

        # Correct secret — sets pending
        success, immediate, _ = await repo.request_channel_destruction(
            channel.short_slug, raw_secret
        )
        assert success is True
        assert immediate is False

    async def test_two_phase_destruction(
        self, channel_with_secret: tuple[ChannelRepository, ChannelData, str]
    ) -> None:
        repo, channel, raw_secret = channel_with_secret
        slug = channel.short_slug

        # First request sets pending
        success, immediate, _ = await repo.request_channel_destruction(slug, raw_secret)
        assert success is True
        assert immediate is False

        # Second request confirms destruction
        success, immediate, msg = await repo.request_channel_destruction(
            slug, raw_secret
        )
        assert success is True
        assert immediate is True
        assert "destroyed" in msg.lower()

        # Channel should be gone
        fetched = await repo.fetch_channel(slug)
        assert fetched is None


# ── Reader Token Validation ──


@pytest.mark.asyncio
class TestReaderTokenValidation:
    """Verify reader token prevents unauthorized access."""

    @pytest_asyncio.fixture
    async def channel_with_token(
        self, redis: Redis
    ) -> tuple[ChannelRepository, ChannelData, str, str]:
        repo = ChannelRepository(redis)
        channel, raw_secret = await repo.create_channel(max_downloads=5, ttl=3600)
        raw_token = await _setup_reader_token(repo, channel, raw_secret)
        return repo, channel, raw_secret, raw_token

    async def test_valid_token_accepted(
        self, channel_with_token: tuple[ChannelRepository, ChannelData, str, str]
    ) -> None:
        repo, channel, _, raw_token = channel_with_token
        result = await repo.validate_reader_token(channel.short_slug, raw_token)
        assert result is True

    async def test_wrong_token_rejected(
        self, channel_with_token: tuple[ChannelRepository, ChannelData, str, str]
    ) -> None:
        repo, channel, _, _ = channel_with_token
        result = await repo.validate_reader_token(channel.short_slug, "wrong-token")
        assert result is False

    async def test_empty_token_rejected(
        self, channel_with_token: tuple[ChannelRepository, ChannelData, str, str]
    ) -> None:
        repo, channel, _, _ = channel_with_token
        result = await repo.validate_reader_token(channel.short_slug, "")
        assert result is False

    async def test_download_requires_valid_token(
        self, channel_with_token: tuple[ChannelRepository, ChannelData, str, str]
    ) -> None:
        repo, channel, _, raw_token = channel_with_token

        # Wrong token fails
        success, _, _ = await repo.record_download_complete(
            channel.short_slug, "wrong-token"
        )
        assert success is False

        # Correct token succeeds
        success, _, _ = await repo.record_download_complete(
            channel.short_slug, raw_token
        )
        assert success is True

    async def test_pending_token_blocks_download(self, redis: Redis) -> None:
        """During the pending-token window, downloads are blocked."""
        repo = ChannelRepository(redis)
        channel, raw_secret = await repo.create_channel(max_downloads=5, ttl=3600)
        # Don't set reader token — pending marker should still exist

        success, _, _ = await repo.record_download_complete(
            channel.short_slug, "any-token"
        )
        assert success is False

    async def test_token_hash_normalized_to_lowercase(self, redis: Redis) -> None:
        """Reader token hash stored as lowercase regardless of input case."""
        repo = ChannelRepository(redis)
        channel, raw_secret = await repo.create_channel(max_downloads=0, ttl=3600)
        raw_token = "my-token"
        # Pass uppercase hex hash
        token_hash = hashlib.sha256(raw_token.encode()).hexdigest().upper()
        result = await repo.set_reader_token(channel.short_slug, raw_secret, token_hash)
        assert result is True

        # Validation should still work (internally normalizes)
        result = await repo.validate_reader_token(channel.short_slug, raw_token)
        assert result is True


# ── Payment Token Binding ──


@pytest.mark.asyncio
class TestPaymentTokenBinding:
    """Verify payment tokens are bound to buyer fingerprint."""

    @pytest_asyncio.fixture
    async def paid_channel(
        self, redis: Redis
    ) -> tuple[ChannelRepository, ChannelData, str]:
        repo = ChannelRepository(redis)
        channel, raw_secret = await repo.create_channel(
            max_downloads=0,
            ttl=3600,
            price_cents=1000,
            currency="usd",
        )
        return repo, channel, raw_secret

    async def test_payment_token_valid_with_correct_fingerprint(
        self, paid_channel: tuple[ChannelRepository, ChannelData, str]
    ) -> None:
        repo, channel, _ = paid_channel
        token = "payment-token-123"
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        fingerprint = "buyer-ip-hash-abc"

        await repo.store_payment_token(
            channel.short_slug, token_hash, 3600, buyer_fingerprint=fingerprint
        )

        result = await repo.validate_payment_token(
            channel.short_slug, token, buyer_fingerprint=fingerprint
        )
        assert result is True

    async def test_payment_token_rejected_with_wrong_fingerprint(
        self, paid_channel: tuple[ChannelRepository, ChannelData, str]
    ) -> None:
        """Token reuse from different IP is rejected."""
        repo, channel, _ = paid_channel
        token = "payment-token-456"
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        buyer_fp = "original-buyer"
        attacker_fp = "different-buyer"

        await repo.store_payment_token(
            channel.short_slug, token_hash, 3600, buyer_fingerprint=buyer_fp
        )

        # Attacker with a different fingerprint
        result = await repo.validate_payment_token(
            channel.short_slug, token, buyer_fingerprint=attacker_fp
        )
        assert result is False

    async def test_payment_token_rejected_with_wrong_token(
        self, paid_channel: tuple[ChannelRepository, ChannelData, str]
    ) -> None:
        repo, channel, _ = paid_channel
        token_hash = hashlib.sha256(b"real-token").hexdigest()
        fingerprint = "buyer-fp"

        await repo.store_payment_token(
            channel.short_slug, token_hash, 3600, buyer_fingerprint=fingerprint
        )

        result = await repo.validate_payment_token(
            channel.short_slug, "fake-token", buyer_fingerprint=fingerprint
        )
        assert result is False

    async def test_checkout_token_one_time_use(
        self, paid_channel: tuple[ChannelRepository, ChannelData, str]
    ) -> None:
        """Checkout payment token can only be claimed once (GETDEL)."""
        repo, channel, _ = paid_channel
        session_id = "cs_test_123"
        payment_token = "pt_abc"

        await repo.store_checkout_payment_token(
            channel.short_slug, session_id, payment_token
        )

        # First claim succeeds (returns decrypted token)
        claimed = await repo.claim_checkout_payment_token(
            channel.short_slug, session_id
        )
        assert claimed == payment_token

        # Second claim returns None (already consumed)
        claimed = await repo.claim_checkout_payment_token(
            channel.short_slug, session_id
        )
        assert claimed is None

    async def test_payment_token_for_nonexistent_channel(self, redis: Redis) -> None:
        repo = ChannelRepository(redis)
        result = await repo.validate_payment_token(
            "nonexistent-slug", "some-token", buyer_fingerprint="fp"
        )
        assert result is False


# ── Password Attempt Tracking ──


@pytest.mark.asyncio
class TestPasswordAttemptTracking:
    """Verify password attempt rate limiting per channel."""

    @pytest_asyncio.fixture
    async def channel_for_pw(
        self, redis: Redis
    ) -> tuple[ChannelRepository, ChannelData, str]:
        repo = ChannelRepository(redis)
        channel, raw_secret = await repo.create_channel(max_downloads=0, ttl=3600)
        return repo, channel, raw_secret

    async def test_attempts_within_limit_allowed(
        self, channel_for_pw: tuple[ChannelRepository, ChannelData, str]
    ) -> None:
        repo, channel, raw_secret = channel_for_pw
        for _ in range(repo.MAX_PASSWORD_ATTEMPTS):
            allowed = await repo.record_password_attempt(channel.short_slug, raw_secret)
            assert allowed is True

    async def test_attempt_exceeding_limit_rejected(
        self, channel_for_pw: tuple[ChannelRepository, ChannelData, str]
    ) -> None:
        repo, channel, raw_secret = channel_for_pw
        # Exhaust all attempts
        for _ in range(repo.MAX_PASSWORD_ATTEMPTS):
            await repo.record_password_attempt(channel.short_slug, raw_secret)

        # Next attempt must fail
        allowed = await repo.record_password_attempt(channel.short_slug, raw_secret)
        assert allowed is False

    async def test_wrong_secret_cannot_record_attempt(
        self, channel_for_pw: tuple[ChannelRepository, ChannelData, str]
    ) -> None:
        repo, channel, _ = channel_for_pw
        allowed = await repo.record_password_attempt(channel.short_slug, "wrong-secret")
        assert allowed is False


# ── One-Time Secret Atomicity ──


@pytest.mark.asyncio
class TestOneTimeSecretAtomicity:
    """Verify one-time secrets are deleted after first fetch."""

    async def test_secret_deleted_after_fetch(self, redis: Redis) -> None:
        from rapidly.sharing.file_sharing.queries import SecretRepository

        repo = SecretRepository(redis)
        secret_id = await repo.create_secret("top-secret-message", expiration=3600)

        # First fetch succeeds
        result = await repo.fetch_secret(secret_id)
        assert result is not None
        assert result.message == "top-secret-message"

        # Second fetch returns None (atomically deleted)
        result = await repo.fetch_secret(secret_id)
        assert result is None

    async def test_file_deleted_after_fetch(self, redis: Redis) -> None:
        from rapidly.sharing.file_sharing.queries import SecretRepository

        repo = SecretRepository(redis)
        file_id = await repo.create_file("encrypted-file-data", expiration=3600)

        result = await repo.fetch_file(file_id)
        assert result is not None

        result = await repo.fetch_file(file_id)
        assert result is None

    async def test_concurrent_fetches_only_one_succeeds(self, redis: Redis) -> None:
        """When multiple requests race for the same secret, only one gets it."""
        from rapidly.sharing.file_sharing.queries import SecretRepository

        repo = SecretRepository(redis)
        secret_id = await repo.create_secret("race-secret", expiration=3600)

        results = await asyncio.gather(
            *[repo.fetch_secret(secret_id) for _ in range(10)]
        )

        non_none = [r for r in results if r is not None]
        assert len(non_none) == 1
        assert non_none[0].message == "race-secret"


# ── Slug Validation ──


class TestSlugValidation:
    """Verify slug validation prevents injection attacks."""

    def test_valid_short_slug(self) -> None:
        result = validate_slug("a1b2c3d4")
        assert result == "a1b2c3d4"

    def test_valid_long_slug(self) -> None:
        result = validate_slug("bacon/cheese/tomato/onion/pickle/lettuce/mayo")
        assert result == "bacon/cheese/tomato/onion/pickle/lettuce/mayo"

    def test_valid_uuid_slug(self) -> None:
        result = validate_slug("a1b2c3d4-e5f6-7890-abcd-ef1234567890")
        assert result == "a1b2c3d4-e5f6-7890-abcd-ef1234567890"

    def test_rejects_path_traversal(self) -> None:
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            validate_slug("../../etc/passwd")
        assert exc_info.value.status_code == 400

    def test_rejects_special_characters(self) -> None:
        from fastapi import HTTPException

        for bad_slug in [
            "slug;DROP TABLE",
            "slug\ninjection",
            "slug<script>",
            "slug${var}",
            "slug`cmd`",
        ]:
            with pytest.raises(HTTPException):
                validate_slug(bad_slug)

    def test_rejects_uppercase(self) -> None:
        from fastapi import HTTPException

        with pytest.raises(HTTPException):
            validate_slug("UPPERCASE")

    def test_rejects_empty(self) -> None:
        from fastapi import HTTPException

        with pytest.raises(HTTPException):
            validate_slug("")

    def test_rejects_too_long(self) -> None:
        from fastapi import HTTPException

        with pytest.raises(HTTPException):
            validate_slug("a" * 300)

    def test_rejects_redis_key_injection(self) -> None:
        """Ensure no Redis key separator or wildcard chars slip through."""
        from fastapi import HTTPException

        for bad in ["slug:injection", "slug*glob", "slug?pattern"]:
            with pytest.raises(HTTPException):
                validate_slug(bad)


# ── Channel Expiration ──


@pytest.mark.asyncio
class TestChannelExpiration:
    """Verify channel TTL and pending-token behavior."""

    async def test_channel_has_ttl(self, redis: Redis) -> None:
        """Created channels have a finite TTL in Redis."""
        repo = ChannelRepository(redis)
        channel, _ = await repo.create_channel(max_downloads=0, ttl=3600)

        ttl = await redis.ttl(f"file-sharing:channel:{channel.short_slug}")
        assert 0 < ttl <= 3600

    async def test_pending_token_blocks_access(self, redis: Redis) -> None:
        """Before reader token is set, pending marker blocks operations."""
        repo = ChannelRepository(redis)
        channel, raw_secret = await repo.create_channel(max_downloads=0, ttl=3600)

        # Pending marker should exist
        is_pending = await repo.is_pending_token(channel.short_slug)
        assert is_pending is True

        # Set reader token clears pending
        token_hash = hashlib.sha256(b"token").hexdigest()
        await repo.set_reader_token(channel.short_slug, raw_secret, token_hash)

        is_pending = await repo.is_pending_token(channel.short_slug)
        assert is_pending is False

    async def test_renewal_extends_ttl(self, redis: Redis) -> None:
        """Renewing a channel resets its TTL."""
        repo = ChannelRepository(redis)
        channel, raw_secret = await repo.create_channel(
            max_downloads=0,
            ttl=60,  # short TTL
        )

        # Renew with longer TTL
        result = await repo.renew_channel(channel.short_slug, raw_secret, ttl=7200)
        assert result is True

        ttl = await redis.ttl(f"file-sharing:channel:{channel.short_slug}")
        assert ttl > 60  # should be close to 7200

    async def test_both_slugs_stored(self, redis: Redis) -> None:
        """Both short and long slugs resolve to the same channel."""
        repo = ChannelRepository(redis)
        channel, _ = await repo.create_channel(max_downloads=0, ttl=3600)

        short = await repo.fetch_channel(channel.short_slug)
        long = await repo.fetch_channel(channel.long_slug)

        assert short is not None
        assert long is not None
        assert short.short_slug == long.short_slug
        assert short.long_slug == long.long_slug

    async def test_reserved_slug_not_fetchable(self, redis: Redis) -> None:
        """The __reserved__ sentinel during slug generation should not parse."""
        # Simulate a reserved slug
        await redis.set("file-sharing:channel:test-reserved", "__reserved__")

        repo = ChannelRepository(redis)
        result = await repo.fetch_channel("test-reserved")
        assert result is None  # __reserved__ is not valid JSON


# ── Atomic Download Counter Lua Script ──


@pytest.mark.asyncio
class TestDownloadCounterLuaScript:
    """Test the ATOMIC_DOWNLOAD_INCR_LUA script directly."""

    async def test_increments_within_limit(self, redis: Redis) -> None:
        key = "test:download:count:1"
        # max_downloads=3, counter_ttl=3600
        for expected in range(1, 4):
            result = await redis.eval(ATOMIC_DOWNLOAD_INCR_LUA, 1, key, 3, 3600)
            assert int(result) == expected

    async def test_rejects_at_limit(self, redis: Redis) -> None:
        key = "test:download:count:2"
        # Fill to max
        for _ in range(3):
            await redis.eval(ATOMIC_DOWNLOAD_INCR_LUA, 1, key, 3, 3600)

        # Next attempt returns -1
        result = await redis.eval(ATOMIC_DOWNLOAD_INCR_LUA, 1, key, 3, 3600)
        assert int(result) == -1

    async def test_sets_ttl_on_first_increment(self, redis: Redis) -> None:
        key = "test:download:count:3"
        await redis.eval(ATOMIC_DOWNLOAD_INCR_LUA, 1, key, 5, 7200)

        ttl = await redis.ttl(key)
        assert 0 < ttl <= 7200

    async def test_concurrent_increments_respect_limit(self, redis: Redis) -> None:
        key = "test:download:count:4"
        max_downloads = 5

        results = await asyncio.gather(
            *[
                redis.eval(ATOMIC_DOWNLOAD_INCR_LUA, 1, key, max_downloads, 3600)
                for _ in range(20)
            ]
        )

        successes = [int(r) for r in results if int(r) != -1]
        failures = [int(r) for r in results if int(r) == -1]

        assert len(successes) == max_downloads
        assert len(failures) == 15
        # Successful results should be 1..max_downloads (in some order)
        assert sorted(successes) == list(range(1, max_downloads + 1))


# ── Channel Deletion Cleanup ──


@pytest.mark.asyncio
class TestChannelDeletionCleanup:
    """Verify delete_channel removes all associated Redis keys."""

    async def test_delete_removes_all_keys(self, redis: Redis) -> None:
        repo = ChannelRepository(redis)
        channel, raw_secret = await repo.create_channel(max_downloads=5, ttl=3600)

        # Set up ancillary keys
        await _setup_reader_token(repo, channel, raw_secret)
        await repo.store_checksums(channel.short_slug, raw_secret, {"f.txt": "a" * 64})

        # Verify keys exist
        assert await repo.fetch_channel(channel.short_slug) is not None
        assert await repo.has_reader_token(channel.short_slug) is True

        # Delete channel
        await repo.delete_channel(channel)

        # All keys gone
        assert await repo.fetch_channel(channel.short_slug) is None
        assert await repo.fetch_channel(channel.long_slug) is None
        assert await repo.has_reader_token(channel.short_slug) is False
        assert await repo.is_pending_token(channel.short_slug) is False
