"""Tests for file sharing channel repository (checksum storage)."""

import pytest
import pytest_asyncio

from rapidly.redis import Redis
from rapidly.sharing.file_sharing.queries import ChannelData, ChannelRepository


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
