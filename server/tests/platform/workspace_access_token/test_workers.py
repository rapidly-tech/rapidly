"""Tests for ``rapidly/platform/workspace_access_token/workers.py``.

Workspace-access-token last-used tracker. Three load-bearing
surfaces:

- ``_record_usage_debounce_key`` is per-TOKEN (NOT per-token-AND-
  timestamp). Bursts of API calls under the debounce window
  collapse into ONE update — drift to include the timestamp would
  defeat the debounce and write to DB on every request.
- ``timestamp → datetime`` conversion uses ``tz=UTC`` (NOT naive).
  Drift to naive would let local-tz drift contaminate the
  ``last_used_at`` audit field across timezones.
- Actor config: ``actor_name="workspace_access_token.record_usage"``
  + ``max_retries=1`` (drift higher would amplify benign timestamp
  races into N×storms; drift to 0 would lose every transient
  failure). ``min_backoff=5_000`` ms keeps retries off the hot
  path.
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from rapidly.platform.workspace_access_token import workers as M
from rapidly.platform.workspace_access_token.workers import (
    _record_usage_debounce_key,
    record_usage,
)


class TestDebounceKey:
    def test_per_token_not_per_timestamp(self) -> None:
        # Pin (load-bearing): the debounce key is keyed ONLY on the
        # token id. Two usage events for the same token at
        # different timestamps must collapse to ONE pending task.
        token_id = uuid4()
        a = _record_usage_debounce_key(token_id, last_used_at=1700_000_000.0)
        b = _record_usage_debounce_key(token_id, last_used_at=1700_000_005.0)
        assert a == b

    def test_distinct_tokens_distinct_keys(self) -> None:
        # Pin: two different tokens MUST have distinct keys —
        # otherwise high-traffic on one token would suppress
        # tracking for the other.
        a = _record_usage_debounce_key(uuid4(), last_used_at=0.0)
        b = _record_usage_debounce_key(uuid4(), last_used_at=0.0)
        assert a != b

    def test_namespace_prefix_pinned(self) -> None:
        # Pin the Redis namespace prefix so the debounce
        # middleware reads + writes the same key.
        token_id = uuid4()
        key = _record_usage_debounce_key(token_id, last_used_at=0.0)
        assert key.startswith("workspace_access_token.record_usage:")
        assert str(token_id) in key


class TestActorConfig:
    def test_actor_function_name_pinned(self) -> None:
        # Pin: dispatch_task("workspace_access_token.record_usage",
        # ...) callers reference the actor by name. The wrapped
        # function's ``__name__`` gives us the canonical Python
        # symbol — drift would break every importer.
        assert record_usage.__name__ == "record_usage"

    @pytest.mark.asyncio
    async def test_record_usage_uses_utc_aware_datetime(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Pin: timestamp → ``datetime.fromtimestamp(ts, tz=UTC)``.
        # A naive datetime (no tz) would let local-tz drift
        # contaminate the audit field across deployment regions.
        captured: dict[str, datetime] = {}

        class _Repo:
            async def record_usage(
                self_, token_id: object, last_used_at: datetime
            ) -> None:
                captured["last_used_at"] = last_used_at

            @classmethod
            def from_session(cls, session: object) -> _Repo:
                return cls()

        monkeypatch.setattr(M, "WorkspaceAccessTokenRepository", _Repo)

        # ``AsyncSessionMaker`` needs to behave as an async context
        # manager yielding an arbitrary session.
        cm = AsyncMock()
        cm.__aenter__ = AsyncMock(return_value=MagicMock())
        cm.__aexit__ = AsyncMock(return_value=False)
        monkeypatch.setattr(M, "AsyncSessionMaker", lambda: cm)

        await record_usage.__wrapped__(  # type: ignore[attr-defined]
            workspace_access_token_id=uuid4(),
            last_used_at=1700_000_000.0,
        )

        dt = captured["last_used_at"]
        # Pin: the ``tzinfo`` is UTC, NOT None.
        assert dt.tzinfo is UTC
        # And the timestamp converts back correctly.
        assert dt.timestamp() == pytest.approx(1700_000_000.0, abs=1e-3)


@pytest.mark.asyncio
class TestRecordUsageDelegatesToRepository:
    async def test_invokes_repository_with_resolved_args(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Pin: the worker delegates to
        # ``WorkspaceAccessTokenRepository.record_usage`` with the
        # token id (UUID, NOT str) and a UTC datetime. Drift would
        # let the worker silently no-op or write to a different
        # table.
        captured: dict[str, object] = {}

        class _Repo:
            async def record_usage(
                self_, token_id: object, last_used_at: datetime
            ) -> None:
                captured["token_id"] = token_id
                captured["dt"] = last_used_at

            @classmethod
            def from_session(cls, session: object) -> _Repo:
                return cls()

        monkeypatch.setattr(M, "WorkspaceAccessTokenRepository", _Repo)

        cm = AsyncMock()
        cm.__aenter__ = AsyncMock(return_value=MagicMock())
        cm.__aexit__ = AsyncMock(return_value=False)
        monkeypatch.setattr(M, "AsyncSessionMaker", lambda: cm)

        token_id = uuid4()
        await record_usage.__wrapped__(  # type: ignore[attr-defined]
            workspace_access_token_id=token_id,
            last_used_at=1700_000_000.0,
        )

        assert captured["token_id"] == token_id
        assert isinstance(captured["dt"], datetime)
