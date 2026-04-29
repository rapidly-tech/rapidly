"""Tests for file sharing channel repository (checksum storage)."""

import pytest
import pytest_asyncio

from rapidly.redis import Redis
from rapidly.sharing.file_sharing.queries import (
    SESSION_KINDS,
    ChannelData,
    ChannelRepository,
    SecretRepository,
    validate_session_kind,
)


@pytest.mark.asyncio
class TestChecksumStorage:
    """Tests for store_checksums / fetch_checksums in ChannelRepository."""

    @pytest_asyncio.fixture
    async def repo_and_channel(
        self, redis: Redis
    ) -> tuple[ChannelRepository, ChannelData, str]:
        """Create a repository and a test channel."""
        repo = ChannelRepository(redis)
        channel, raw_secret = await repo.create_channel(max_downloads=0, ttl=3600)
        return repo, channel, raw_secret

    async def test_store_and_fetch_checksums(
        self, repo_and_channel: tuple[ChannelRepository, ChannelData, str]
    ) -> None:
        repo, channel, raw_secret = repo_and_channel
        checksums = {"file1.txt": "a" * 64, "file2.txt": "b" * 64}

        # Store with valid secret
        success = await repo.store_checksums(channel.short_slug, raw_secret, checksums)
        assert success is True

        # Set reader token so we can fetch
        import hashlib

        token = "test-reader-token-123"
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        await repo.set_reader_token(channel.short_slug, raw_secret, token_hash)

        # Fetch with valid reader token
        result = await repo.fetch_checksums(channel.short_slug, token)
        assert result is not None
        assert result == checksums

    async def test_store_rejects_wrong_secret(
        self, repo_and_channel: tuple[ChannelRepository, ChannelData, str]
    ) -> None:
        repo, channel, _raw_secret = repo_and_channel
        success = await repo.store_checksums(
            channel.short_slug, "wrong-secret", {"f.txt": "a" * 64}
        )
        assert success is False

    async def test_store_rejects_nonexistent_slug(self, redis: Redis) -> None:
        repo = ChannelRepository(redis)
        success = await repo.store_checksums(
            "nonexistent", "secret", {"f.txt": "a" * 64}
        )
        assert success is False

    async def test_fetch_rejects_invalid_reader_token(
        self, repo_and_channel: tuple[ChannelRepository, ChannelData, str]
    ) -> None:
        repo, channel, raw_secret = repo_and_channel
        # Store checksums
        await repo.store_checksums(channel.short_slug, raw_secret, {"f.txt": "a" * 64})
        # Set a reader token
        import hashlib

        token = "valid-token"
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        await repo.set_reader_token(channel.short_slug, raw_secret, token_hash)

        # Fetch with wrong token
        result = await repo.fetch_checksums(channel.short_slug, "wrong-token")
        assert result is None

    async def test_fetch_returns_none_when_no_checksums(
        self, repo_and_channel: tuple[ChannelRepository, ChannelData, str]
    ) -> None:
        repo, channel, raw_secret = repo_and_channel
        import hashlib

        token = "test-token"
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        await repo.set_reader_token(channel.short_slug, raw_secret, token_hash)

        result = await repo.fetch_checksums(channel.short_slug, token)
        assert result is None

    async def test_fetch_returns_none_for_nonexistent_slug(self, redis: Redis) -> None:
        repo = ChannelRepository(redis)
        result = await repo.fetch_checksums("nonexistent", "some-token")
        assert result is None


class TestSessionKind:
    """Tests for the session_kind field on ChannelData (PR 1)."""

    def _base_fields(self) -> dict[str, str | int]:
        """Minimum fields required by ChannelData / from_dict."""
        return {
            "secret": "hashed-secret",
            "long_slug": "long-slug-abc",
            "short_slug": "short-abc",
        }

    def test_defaults_to_file(self) -> None:
        """A ChannelData built without specifying session_kind is a file session."""
        channel = ChannelData(secret="s", long_slug="l", short_slug="sh")
        assert channel.session_kind == "file"

    def test_roundtrip_preserves_explicit_kind(self) -> None:
        """to_dict() → from_dict() preserves session_kind."""
        channel = ChannelData(
            secret="s", long_slug="l", short_slug="sh", session_kind="file"
        )
        reloaded = ChannelData.from_dict(channel.to_dict())
        assert reloaded.session_kind == "file"

    def test_from_dict_missing_key_defaults_to_file(self) -> None:
        """Redis entries written before this field existed read back as 'file'.

        This is the backward-compatibility guarantee — no migration needed.
        """
        # Simulate a legacy payload: no 'session_kind' key present.
        legacy_payload = self._base_fields()
        assert "session_kind" not in legacy_payload

        channel = ChannelData.from_dict(legacy_payload)
        assert channel.session_kind == "file"

    def test_from_dict_accepts_unknown_kind_without_raising(self) -> None:
        """from_dict must not validate — it must always succeed on stored data.

        Validation belongs at construction sites (API handlers), not at the
        storage-read boundary. If we ever store a bogus kind, we want the
        row to still be readable so an operator can investigate and fix it.
        """
        payload = {**self._base_fields(), "session_kind": "bogus-kind"}
        channel = ChannelData.from_dict(payload)
        assert channel.session_kind == "bogus-kind"

    def test_session_kinds_contains_file(self) -> None:
        assert "file" in SESSION_KINDS

    def test_validate_session_kind_accepts_file(self) -> None:
        validate_session_kind("file")  # must not raise

    def test_validate_session_kind_rejects_unknown(self) -> None:
        with pytest.raises(ValueError, match="Unknown session_kind"):
            validate_session_kind("bogus-kind")


@pytest.mark.asyncio
class TestNoServerCreatedCounter:
    """Tests for the URL-fragment (no-server) share counter on SecretRepository.

    The split mirrors ``increment_created_count`` exactly: the global
    key always bumps so the public ""shares so far"" tally includes
    every no-server share, while the per-workspace key only bumps when
    a workspace_id is attributed — keeping anonymous traffic out of
    workspace dashboards.
    """

    async def test_anonymous_ping_only_bumps_global(self, redis: Redis) -> None:
        repo = SecretRepository(redis)
        start_global = await repo.get_no_server_created_count()
        start_ws = await repo.get_workspace_no_server_created_count("ws-anon-1")

        await repo.increment_no_server_created_count(workspace_id=None)

        assert await repo.get_no_server_created_count() == start_global + 1
        # Workspace counters untouched by anonymous activity.
        assert await repo.get_workspace_no_server_created_count("ws-anon-1") == start_ws

    async def test_workspace_ping_bumps_both(self, redis: Redis) -> None:
        repo = SecretRepository(redis)
        ws = "ws-counter-test"
        start_global = await repo.get_no_server_created_count()
        start_ws = await repo.get_workspace_no_server_created_count(ws)

        await repo.increment_no_server_created_count(workspace_id=ws)

        assert await repo.get_no_server_created_count() == start_global + 1
        assert await repo.get_workspace_no_server_created_count(ws) == start_ws + 1

    async def test_get_returns_zero_for_unseen_workspace(self, redis: Redis) -> None:
        repo = SecretRepository(redis)
        assert await repo.get_workspace_no_server_created_count("never-pinged-ws") == 0

    async def test_increment_invalidates_stats_cache(self, redis: Redis) -> None:
        """The 15s ``_STATS_CACHE_KEY`` must be cleared on every bump,
        so the very next ``/stats`` poll sees the new total instead of
        a stale cached value."""
        repo = SecretRepository(redis)
        # Seed a cached total to verify it gets invalidated.
        await redis.setex(repo._STATS_CACHE_KEY, 15, "999")
        assert await redis.get(repo._STATS_CACHE_KEY) is not None

        await repo.increment_no_server_created_count()

        assert await redis.get(repo._STATS_CACHE_KEY) is None

    async def test_no_server_counter_is_separate_from_secrets_created(
        self, redis: Redis
    ) -> None:
        """Each counter must be independent — bumping no-server must
        not pollute ``secrets_created`` (""things stored on our server"")
        and vice versa."""
        repo = SecretRepository(redis)
        start_secrets = await repo.get_created_count()
        start_no_server = await repo.get_no_server_created_count()

        await repo.increment_no_server_created_count()

        assert await repo.get_created_count() == start_secrets
        assert await repo.get_no_server_created_count() == start_no_server + 1
