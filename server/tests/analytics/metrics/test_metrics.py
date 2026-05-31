"""Tests for ``rapidly/analytics/metrics/metrics.py`` module-level
helpers.

Three load-bearing surfaces:

- ``MetricType`` enum carries the four documented display
  classes used by the dashboard renderer to format axis labels:
  ``scalar`` / ``currency`` / ``currency_sub_cent`` /
  ``percentage``. Drift to drop one would crash the renderer
  with KeyError when a metric returns the missing variant.
- ``cumulative_sum`` aggregates the named field across a list
  of ``MetricsPeriod``s and treats ``None`` values as 0 (drift
  would TypeError on the first None and break the dashboard
  total for any metric with sparse rows).
- ``cumulative_last`` returns the LAST period's value (or 0
  when None / no periods touched). Drift to return the FIRST
  would mis-display "current balance"-style metrics.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest

from rapidly.analytics.metrics.metrics import (
    MetricType,
    cumulative_last,
    cumulative_sum,
)


def _period(value: Any) -> Any:
    p = MagicMock()
    p.foo = value
    return p


class TestMetricTypeEnum:
    def test_documented_four_variants(self) -> None:
        # Pin: scalar / currency / currency_sub_cent /
        # percentage. Drift to drop one would crash the dashboard
        # renderer when a metric returns the missing variant.
        assert {m.value for m in MetricType} == {
            "scalar",
            "currency",
            "currency_sub_cent",
            "percentage",
        }


class TestCumulativeSum:
    def test_sums_across_periods(self) -> None:
        # Pin: simple sum across periods.
        assert (
            cumulative_sum(
                [_period(1), _period(2), _period(3)],
                "foo",
            )
            == 6
        )

    def test_treats_none_as_zero(self) -> None:
        # Pin: drift to bare addition would TypeError on the
        # first None and break the dashboard total for any
        # metric with sparse rows (e.g. days with no payments).
        assert cumulative_sum([_period(1), _period(None), _period(3)], "foo") == 4

    def test_empty_iterable_returns_zero(self) -> None:
        # Pin: ``sum()`` of an empty iterable returns 0 — drift
        # to require at least one period would crash the
        # dashboard on workspaces with no data yet.
        assert cumulative_sum([], "foo") == 0


class TestCumulativeLast:
    def test_returns_last_period_value(self) -> None:
        # Pin: returns the LAST period's value (cumulative
        # totals like "running balance" need this). Drift to
        # FIRST would mis-display every cumulative dashboard
        # tile.
        assert cumulative_last([_period(1), _period(2), _period(3)], "foo") == 3

    def test_treats_last_none_as_zero(self) -> None:
        # Pin: drift to return None would surface a None-typed
        # value in the dashboard render path that Pydantic
        # serialises as null (broken UI tile).
        assert cumulative_last([_period(1), _period(None)], "foo") == 0

    def test_single_period(self) -> None:
        assert cumulative_last([_period(42)], "foo") == 42


@pytest.mark.asyncio
class TestConfigureSessionTimezoneFallback:
    """Pin the PG-fallback path for tzdata divergence.

    The HTTP layer can't normally reach this branch — pydantic's
    ``TimeZoneName`` rejects the deprecated aliases (``Asia/Saigon``,
    ``Asia/Calcutta``) that PG used to choke on. The fallback is
    still load-bearing for any direct call site and for any future
    tzdata regression where a name accepted by ``TimeZoneName`` is
    unknown to PG.

    Two assertions:

    - When ``pg_timezone_names`` does NOT contain the requested
      zone (scalar returns ``None``), the function returns
      ``"UTC"`` AND calls ``set_config("TimeZone", "UTC", True)``
      — NOT the original requested string. Drift to passing the
      original would re-introduce the original Sentry bug.
    - When ``pg_timezone_names`` DOES contain the requested zone
      (scalar returns ``1``), the function returns the requested
      string unchanged AND passes it to ``set_config``.
    """

    @staticmethod
    def _fake_session(*, pg_knows: bool) -> tuple[Any, list[str]]:
        set_config_binds: list[str] = []

        class _FakeSession:
            async def scalar(self_, statement: Any, params: Any | None = None) -> Any:
                return 1 if pg_knows else None

            async def execute(self_, statement: Any) -> Any:
                stmt_text = str(statement)
                if "set_config" in stmt_text:
                    compiled = str(
                        statement.compile(compile_kwargs={"literal_binds": True})
                    )
                    set_config_binds.append(compiled)
                return MagicMock()

        return _FakeSession(), set_config_binds

    async def test_unknown_timezone_falls_back_to_utc(self) -> None:
        from rapidly.analytics.metrics.queries import MetricsQueryService

        session, set_config_binds = self._fake_session(pg_knows=False)
        svc = MetricsQueryService(session)
        applied = await svc.configure_session_timezone("Made/Up_Zone")

        assert applied == "UTC"
        # The set_config bind must be 'UTC', NOT the requested
        # string — otherwise PG would 500 with "invalid value
        # for parameter TimeZone".
        assert any("'UTC'" in b for b in set_config_binds)
        assert not any("'Made/Up_Zone'" in b for b in set_config_binds)

    async def test_known_timezone_passes_through(self) -> None:
        from rapidly.analytics.metrics.queries import MetricsQueryService

        session, set_config_binds = self._fake_session(pg_knows=True)
        svc = MetricsQueryService(session)
        applied = await svc.configure_session_timezone("America/New_York")

        assert applied == "America/New_York"
        assert any("'America/New_York'" in b for b in set_config_binds)
