"""Tests for ``rapidly/admin/workspaces/analytics.py``.

Pure scoring & percentile helpers used in the moderator's
account-review dashboard. Three load-bearing surfaces:

- ``calculate_risk_percentiles`` is the hand-rolled P50/P90
  computation. Even-count P50 averages the two middle values;
  odd-count picks the middle. P90 uses ``int(0.9 * n)`` clamped
  to ``n - 1``. Empty list returns ``(0.0, 0.0)``. Drift in
  index math would silently mis-bucket workspaces in the
  moderation queue.
- ``determine_risk_level`` thresholds are green ``< 65``,
  yellow ``[65, 75)``, red ``>= 75``. Drift would mis-color
  workspaces in the dashboard, leading moderators to chase the
  wrong cases first.
- ``calculate_setup_score`` is a 0-6 sum (one point each for
  webhooks > 0, tokens > 0, products > 0, identity verified,
  Stripe charges enabled, Stripe payouts enabled). Drift to
  uneven weighting would silently change the moderator's UX
  for "is this account fully set up".
- ``check_account_enabled`` returns ``(False, False)`` when no
  account is attached. Drift to raise / coerce would 500 the
  detail page on freshly-onboarded workspaces.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from rapidly.admin.workspaces.analytics import (
    PaymentAnalyticsService,
    WorkspaceSetupAnalyticsService,
)


class TestCalculateRiskPercentiles:
    def test_empty_returns_zeroes(self) -> None:
        # Pin: empty list → ``(0.0, 0.0)``. Drift to raise would
        # 500 the detail page when a workspace has no payments.
        p50, p90 = PaymentAnalyticsService.calculate_risk_percentiles([])
        assert p50 == 0.0
        assert p90 == 0.0

    def test_odd_count_uses_middle(self) -> None:
        # Pin: 3 values → P50 picks the middle (50). Drift to
        # average would shift the median for odd counts.
        p50, _ = PaymentAnalyticsService.calculate_risk_percentiles([10, 50, 90])
        assert p50 == 50

    def test_even_count_averages_two_middle(self) -> None:
        # Pin: 4 values → P50 averages the two middle (40, 60).
        # Drift to single-pick would silently shift the median.
        p50, _ = PaymentAnalyticsService.calculate_risk_percentiles([10, 40, 60, 90])
        assert p50 == 50

    def test_p90_uses_int_floor_index(self) -> None:
        # Pin: P90 = ``sorted[int(0.9 * n)]``. For n=10, index=9
        # → the largest value.
        scores = [10.0, 20.0, 30.0, 40.0, 50.0, 60.0, 70.0, 80.0, 90.0, 100.0]
        _, p90 = PaymentAnalyticsService.calculate_risk_percentiles(scores)
        assert p90 == 100.0

    def test_p90_clamped_to_last_index_for_small_lists(self) -> None:
        # Pin: ``int(0.9 * n) >= n`` is clamped to ``n - 1``.
        # For n=1, index=0 (last); avoids IndexError. Drift to
        # raw index would crash on single-payment workspaces.
        _, p90 = PaymentAnalyticsService.calculate_risk_percentiles([42.0])
        assert p90 == 42.0

    def test_input_list_not_mutated(self) -> None:
        # Pin: caller's list is NOT sorted in-place. Drift to
        # in-place sort would silently mutate caller state.
        scores = [50.0, 10.0, 90.0]
        before = list(scores)
        PaymentAnalyticsService.calculate_risk_percentiles(scores)
        assert scores == before


class TestDetermineRiskLevel:
    def test_below_65_is_green(self) -> None:
        # Pin: green for P90 < 65.
        assert PaymentAnalyticsService.determine_risk_level(0) == "green"
        assert PaymentAnalyticsService.determine_risk_level(64.99) == "green"

    def test_65_inclusive_to_75_exclusive_is_yellow(self) -> None:
        # Pin: yellow band is ``[65, 75)``. Drift on either bound
        # would mis-color workspaces in the dashboard.
        assert PaymentAnalyticsService.determine_risk_level(65) == "yellow"
        assert PaymentAnalyticsService.determine_risk_level(74.99) == "yellow"

    def test_75_and_above_is_red(self) -> None:
        # Pin: red is ``>= 75`` (matches the high-risk threshold
        # in the list query).
        assert PaymentAnalyticsService.determine_risk_level(75) == "red"
        assert PaymentAnalyticsService.determine_risk_level(100) == "red"


class TestCalculateSetupScore:
    def test_zero_signals_zero_score(self) -> None:
        # Pin: 0/6 score for a brand-new workspace.
        assert (
            WorkspaceSetupAnalyticsService.calculate_setup_score(
                webhooks_count=0,
                org_tokens_count=0,
                products_count=0,
                user_verified=False,
                account_charges_enabled=False,
                account_payouts_enabled=False,
            )
            == 0
        )

    def test_full_setup_six_points(self) -> None:
        # Pin: maxes at 6 (matches the count of signals; if
        # someone adds a new signal, this test forces a
        # deliberate update of the score range).
        assert (
            WorkspaceSetupAnalyticsService.calculate_setup_score(
                webhooks_count=3,
                org_tokens_count=1,
                products_count=10,
                user_verified=True,
                account_charges_enabled=True,
                account_payouts_enabled=True,
            )
            == 6
        )

    def test_each_signal_worth_one_point(self) -> None:
        # Pin: equal-weight scoring. Drift to weighted (e.g.
        # double-count `user_verified`) would silently change
        # the moderator's UX without anyone noticing.
        cases: list[dict[str, int | bool]] = [
            {"webhooks_count": 1},
            {"org_tokens_count": 1},
            {"products_count": 1},
            {"user_verified": True},
            {"account_charges_enabled": True},
            {"account_payouts_enabled": True},
        ]
        for case in cases:
            kwargs: dict[str, int | bool] = {
                "webhooks_count": 0,
                "org_tokens_count": 0,
                "products_count": 0,
                "user_verified": False,
                "account_charges_enabled": False,
                "account_payouts_enabled": False,
                **case,
            }
            assert (
                WorkspaceSetupAnalyticsService.calculate_setup_score(**kwargs)  # type: ignore[arg-type]
                == 1
            ), case

    def test_count_above_one_still_one_point(self) -> None:
        # Pin: signals are PRESENCE flags, not magnitudes. Drift
        # to count-based scoring would let a workspace with 100
        # webhooks dominate the dashboard.
        score = WorkspaceSetupAnalyticsService.calculate_setup_score(
            webhooks_count=100,
            org_tokens_count=0,
            products_count=0,
            user_verified=False,
            account_charges_enabled=False,
            account_payouts_enabled=False,
        )
        assert score == 1


class TestCheckAccountEnabled:
    @pytest.mark.asyncio
    async def test_returns_false_pair_when_no_account(self) -> None:
        # Pin: missing account → ``(False, False)`` (no crash).
        # Drift to raise would 500 the workspace detail page on
        # freshly-onboarded entities.
        service = WorkspaceSetupAnalyticsService(session=MagicMock())
        workspace = MagicMock()
        workspace.account = None

        result = await service.check_account_enabled(workspace)
        assert result == (False, False)

    @pytest.mark.asyncio
    async def test_uses_account_flags_when_present(self) -> None:
        # Pin: returns ``(charges_enabled, payouts_enabled)`` from
        # the attached Stripe account object.
        service = WorkspaceSetupAnalyticsService(session=MagicMock())
        workspace = MagicMock()
        workspace.account.charges_enabled = True
        workspace.account.payouts_enabled = False

        result = await service.check_account_enabled(workspace)
        assert result == (True, False)


class TestCheckUserVerifiedInStripe:
    @pytest.mark.asyncio
    async def test_returns_false_when_no_account(self) -> None:
        service = WorkspaceSetupAnalyticsService(session=MagicMock())
        workspace = MagicMock()
        workspace.account = None
        assert await service.check_user_verified_in_stripe(workspace) is False

    @pytest.mark.asyncio
    async def test_returns_false_when_no_stripe_id(self) -> None:
        # Pin: an account with no Stripe id is NOT verified —
        # drift would mark un-onboarded workspaces as verified
        # in the dashboard.
        service = WorkspaceSetupAnalyticsService(session=MagicMock())
        workspace = MagicMock()
        workspace.account.stripe_id = None
        assert await service.check_user_verified_in_stripe(workspace) is False

    @pytest.mark.asyncio
    async def test_uses_charges_enabled_flag(self) -> None:
        # Pin: verification check is gated on
        # ``charges_enabled`` (NOT ``payouts_enabled``). Drift
        # to check payouts would mark accounts that can charge
        # but haven't completed Stripe payouts onboarding as
        # unverified, blocking the moderation flow.
        service = WorkspaceSetupAnalyticsService(session=MagicMock())
        workspace = MagicMock()
        workspace.account.stripe_id = "acct_123"
        workspace.account.charges_enabled = True
        assert await service.check_user_verified_in_stripe(workspace) is True
