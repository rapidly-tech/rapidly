"""Tests for ``rapidly/analytics/external_event/workers.py``.

Daily prune cron — deletes external_event rows older than 30 days.
Three load-bearing surfaces:

- 30-day retention window. Drift down would lose audit data
  premature (Stripe webhook receipts, GitHub secret-scanning
  alerts, etc. — needed for incident postmortems). Drift up
  balloons the table and slows every analytics query.
- Daily midnight cron schedule. Drift to a busier time slot
  would compete with billing reconciliation jobs.
- ``max_retries=0`` — the prune is idempotent (a missed run
  just gets caught the next day). Retries would amplify bursty
  Postgres load with no benefit.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest

from rapidly.analytics.external_event import workers as M
from rapidly.analytics.external_event.workers import external_event_prune


@pytest.mark.asyncio
class TestExternalEventPrune:
    async def _setup(
        self,
        monkeypatch: pytest.MonkeyPatch,
        *,
        now: datetime,
    ) -> tuple[MagicMock, dict[str, datetime]]:
        captured: dict[str, datetime] = {}

        repo = MagicMock()

        async def fake_delete_before(threshold: datetime) -> None:
            captured["threshold"] = threshold

        repo.delete_before = fake_delete_before
        repo_cls = MagicMock()
        repo_cls.from_session = MagicMock(return_value=repo)
        monkeypatch.setattr(M, "ExternalEventRepository", repo_cls)

        cm = AsyncMock()
        cm.__aenter__ = AsyncMock(return_value=MagicMock())
        cm.__aexit__ = AsyncMock(return_value=False)
        monkeypatch.setattr(M, "AsyncSessionMaker", lambda: cm)

        monkeypatch.setattr(M, "now_utc", lambda: now)
        return repo, captured

    async def test_deletes_rows_older_than_30_days(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Pin: the threshold is exactly ``now_utc() - 30 days``.
        # Drift down loses audit data prematurely (Stripe webhook
        # receipts, GitHub secret-scanning alerts); drift up
        # balloons the table.
        from datetime import UTC

        now = datetime(2026, 5, 1, 0, 0, 0, tzinfo=UTC)
        _, captured = await self._setup(monkeypatch, now=now)

        await external_event_prune.__wrapped__()  # type: ignore[attr-defined]

        threshold = captured["threshold"]
        assert (now - threshold) == timedelta(days=30)

    async def test_threshold_is_relative_to_now_utc(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Pin: ``now_utc()`` is called fresh at run time (NOT
        # captured at import time). A regression to a captured
        # constant would mean the prune cutoff stays stuck on
        # the worker's boot date and quickly stops pruning.
        from datetime import UTC

        first_run = datetime(2026, 1, 1, tzinfo=UTC)
        _, cap1 = await self._setup(monkeypatch, now=first_run)
        await external_event_prune.__wrapped__()  # type: ignore[attr-defined]

        second_run = datetime(2026, 6, 1, tzinfo=UTC)
        _, cap2 = await self._setup(monkeypatch, now=second_run)
        await external_event_prune.__wrapped__()  # type: ignore[attr-defined]

        assert cap1["threshold"] != cap2["threshold"]
        assert (second_run - cap2["threshold"]) == timedelta(days=30)
