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
    _CLEANUP_HOUR,
    _CLEANUP_MINUTE,
    _record_usage_debounce_key,
    record_usage,
    workspace_access_token_hard_delete_aged_soft_deletes,
    workspace_access_token_soft_delete_expired,
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


class TestCleanupSchedule:
    def test_runs_at_midnight_utc(self) -> None:
        # Pin the cleanup schedule. A drift to e.g. business
        # hours would compete with the billing reconciliation
        # + analytics rollups that all share the midnight UTC
        # off-peak window (auth, customer_session, login_code,
        # member_session, customer_session_code, and now this
        # token cleanup all converge here).
        assert _CLEANUP_HOUR == 0
        assert _CLEANUP_MINUTE == 0


@pytest.mark.asyncio
class TestSoftDeleteExpiredActor:
    async def test_delegates_to_service_soft_delete_expired(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Pin: the actor opens a session and calls
        # ``workspace_access_token_service.soft_delete_expired
        # (session)``. Drift would silently stop the cleanup —
        # expired tokens would re-accumulate on the operator-
        # visible list forever.
        captured: dict[str, object] = {}

        async def fake_soft_delete_expired(session: object) -> int:
            captured["session"] = session
            return 0

        fake_service = MagicMock()
        fake_service.soft_delete_expired = fake_soft_delete_expired
        monkeypatch.setattr(M, "workspace_access_token_service", fake_service)

        session_obj = MagicMock(name="session")
        cm = AsyncMock()
        cm.__aenter__ = AsyncMock(return_value=session_obj)
        cm.__aexit__ = AsyncMock(return_value=False)
        monkeypatch.setattr(M, "AsyncSessionMaker", lambda: cm)

        await workspace_access_token_soft_delete_expired.__wrapped__()  # type: ignore[attr-defined]

        assert captured["session"] is session_obj

    async def test_silent_when_zero_rows_affected(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Pin: the ``if rowcount:`` log gate means a zero-row
        # tick produces no log line. Drift to log on every tick
        # would spam the logs daily (every workspace's cron
        # fires this even when there's nothing to do).
        fake_service = MagicMock()
        fake_service.soft_delete_expired = AsyncMock(return_value=0)
        monkeypatch.setattr(M, "workspace_access_token_service", fake_service)

        cm = AsyncMock()
        cm.__aenter__ = AsyncMock(return_value=MagicMock())
        cm.__aexit__ = AsyncMock(return_value=False)
        monkeypatch.setattr(M, "AsyncSessionMaker", lambda: cm)

        # Capture the structlog log calls so we can assert
        # no .info() fired for the zero-row case.
        fake_log = MagicMock()
        monkeypatch.setattr(M, "_log", fake_log)

        await workspace_access_token_soft_delete_expired.__wrapped__()  # type: ignore[attr-defined]

        fake_log.info.assert_not_called()

    async def test_logs_rowcount_when_rows_affected(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Pin: the ``if rowcount:`` log gate fires the count
        # so operators tailing the worker log can grep for
        # daily cleanup volume.
        fake_service = MagicMock()
        fake_service.soft_delete_expired = AsyncMock(return_value=7)
        monkeypatch.setattr(M, "workspace_access_token_service", fake_service)

        cm = AsyncMock()
        cm.__aenter__ = AsyncMock(return_value=MagicMock())
        cm.__aexit__ = AsyncMock(return_value=False)
        monkeypatch.setattr(M, "AsyncSessionMaker", lambda: cm)

        fake_log = MagicMock()
        monkeypatch.setattr(M, "_log", fake_log)

        await workspace_access_token_soft_delete_expired.__wrapped__()  # type: ignore[attr-defined]

        fake_log.info.assert_called_once_with(
            "workspace_access_token.expired_cleanup",
            soft_deleted=7,
        )


@pytest.mark.asyncio
class TestHardDeleteAgedSoftDeletesActor:
    """Daily cron that permanently deletes tokens soft-deleted
    by the expiry path more than
    ``settings.WORKSPACE_ACCESS_TOKEN_HARD_DELETE_AFTER`` ago.

    Pinned: delegation, silent on zero rows, distinct log
    event name from the soft-delete actor (operators tail
    different events for different lifecycle phases).
    """

    async def test_delegates_to_service_hard_delete(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        captured: dict[str, object] = {}

        async def fake_hard_delete(session: object) -> int:
            captured["session"] = session
            return 0

        fake_service = MagicMock()
        fake_service.hard_delete_aged_soft_deletes = fake_hard_delete
        monkeypatch.setattr(M, "workspace_access_token_service", fake_service)

        session_obj = MagicMock(name="session")
        cm = AsyncMock()
        cm.__aenter__ = AsyncMock(return_value=session_obj)
        cm.__aexit__ = AsyncMock(return_value=False)
        monkeypatch.setattr(M, "AsyncSessionMaker", lambda: cm)

        await workspace_access_token_hard_delete_aged_soft_deletes.__wrapped__()  # type: ignore[attr-defined]
        assert captured["session"] is session_obj

    async def test_silent_when_zero_rows_affected(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Daily cron must not log-spam when nothing is purged.
        fake_service = MagicMock()
        fake_service.hard_delete_aged_soft_deletes = AsyncMock(return_value=0)
        monkeypatch.setattr(M, "workspace_access_token_service", fake_service)

        cm = AsyncMock()
        cm.__aenter__ = AsyncMock(return_value=MagicMock())
        cm.__aexit__ = AsyncMock(return_value=False)
        monkeypatch.setattr(M, "AsyncSessionMaker", lambda: cm)

        fake_log = MagicMock()
        monkeypatch.setattr(M, "_log", fake_log)

        await workspace_access_token_hard_delete_aged_soft_deletes.__wrapped__()  # type: ignore[attr-defined]

        fake_log.info.assert_not_called()

    async def test_logs_rowcount_when_rows_affected(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Pin the distinct log event name. Operators tailing
        # for cleanup volume should see "purged" (this cron's
        # event) distinct from "expired_cleanup" (the soft-
        # delete cron's event) — they're two phases of the
        # token lifecycle and conflating them would obscure
        # the retention-window behaviour.
        fake_service = MagicMock()
        fake_service.hard_delete_aged_soft_deletes = AsyncMock(return_value=3)
        monkeypatch.setattr(M, "workspace_access_token_service", fake_service)

        cm = AsyncMock()
        cm.__aenter__ = AsyncMock(return_value=MagicMock())
        cm.__aexit__ = AsyncMock(return_value=False)
        monkeypatch.setattr(M, "AsyncSessionMaker", lambda: cm)

        fake_log = MagicMock()
        monkeypatch.setattr(M, "_log", fake_log)

        await workspace_access_token_hard_delete_aged_soft_deletes.__wrapped__()  # type: ignore[attr-defined]

        fake_log.info.assert_called_once_with(
            "workspace_access_token.aged_soft_deletes_purged",
            hard_deleted=3,
        )
