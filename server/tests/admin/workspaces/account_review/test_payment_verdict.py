"""Tests for ``rapidly/admin/workspaces/account_review/_payment_verdict.py``.

Three load-bearing surfaces:

- ``_format_currency`` divides by 100 (cents → dollars) and emits
  comma-thousands + 2-decimal format. Drift to wrong divisor or
  format would mis-display every amount in the review dashboard.
- The constructor unpacks the ``PaymentStatistics`` dataclass into
  individual attributes. Drift to drop a field would crash on
  render.
- ``render()`` wraps the verdict in DaisyUI ``card-body`` chrome
  AND only emits per-payment risk metrics when
  ``payment_count > 0`` (drift would crash on workspaces with no
  payments). The balance display goes ``text-red-600`` when
  ``transfer_sum < 0`` and ``text-green-600`` otherwise — drift
  would invert the financial-state cue.
"""

from __future__ import annotations

from unittest.mock import MagicMock

from tagflow import document

from rapidly.admin.workspaces.account_review._payment_verdict import (
    PaymentVerdict,
)
from rapidly.admin.workspaces.types import PaymentStatistics


def _stats(
    *,
    payment_count: int = 0,
    p50_risk: float = 0.0,
    p90_risk: float = 0.0,
    transfer_sum: int = 0,
    total_payment_amount: int = 0,
) -> PaymentStatistics:
    return PaymentStatistics(
        payment_count=payment_count,
        p50_risk=p50_risk,
        p90_risk=p90_risk,
        transfer_sum=transfer_sum,
        total_payment_amount=total_payment_amount,
    )


def _render(verdict: PaymentVerdict) -> str:
    with document() as doc:
        with verdict.render():
            pass
    return doc.to_html()


class TestFormatCurrency:
    def test_divides_by_100_for_cents_to_dollars(self) -> None:
        # Pin: amounts are stored in cents (Stripe convention).
        # Drift to dollars-already would over-format every amount
        # by 100x in the moderator's view.
        verdict = PaymentVerdict(_stats())
        assert verdict._format_currency(12345) == "$123.45"

    def test_two_decimal_places(self) -> None:
        # Pin: ``.2f`` pads $123 to $123.00. Drift to bare ``f""``
        # would strip the trailing zeroes.
        verdict = PaymentVerdict(_stats())
        assert verdict._format_currency(12300) == "$123.00"

    def test_thousands_separator(self) -> None:
        # Pin: ``,``-thousands. Drift would render large
        # transfers as opaque digit strings.
        verdict = PaymentVerdict(_stats())
        assert verdict._format_currency(123_456_789) == "$1,234,567.89"

    def test_negative_amount_keeps_minus_prefix(self) -> None:
        verdict = PaymentVerdict(_stats())
        assert verdict._format_currency(-5000) == "$-50.00"


class TestConstructorUnpacksStatistics:
    def test_attributes_match_dataclass_fields(self) -> None:
        # Pin: each PaymentStatistics field is unpacked onto the
        # instance. Drift to add a field without binding would
        # crash on render with AttributeError.
        stats = _stats(
            payment_count=42,
            p50_risk=55.5,
            p90_risk=80.1,
            transfer_sum=10_000,
            total_payment_amount=999_999,
        )
        verdict = PaymentVerdict(stats)
        assert verdict.payment_count == 42
        assert verdict.p50_risk == 55.5
        assert verdict.p90_risk == 80.1
        assert verdict.transfer_sum == 10_000
        assert verdict.total_payment_amount == 999_999

    def test_render_defaults_no_actions(self) -> None:
        # Pin: ``show_actions`` defaults to False — the verdict
        # is render-only when called without a request. Drift to
        # default-True would emit the destructive Approve/Deny
        # buttons on every workspace detail render.
        verdict = PaymentVerdict(_stats())
        assert verdict.show_actions is False
        assert verdict.workspace is None
        assert verdict.request is None
        assert verdict.validation_error is None


class TestRenderEmptyPaymentsCase:
    def test_zero_payments_does_not_render_p50_p90(self) -> None:
        # Pin: per-payment risk metrics ONLY render when count >
        # 0. Drift to render unconditionally would surface "P50
        # 0.0" on freshly-onboarded workspaces — a confusing
        # signal and a potential div-by-zero in upstream
        # callers.
        verdict = PaymentVerdict(_stats(payment_count=0))
        html = _render(verdict)
        assert "P50 Risk Score" not in html
        assert "P90 Risk Score" not in html
        # Total Payments row still shown.
        assert "Total Payments" in html

    def test_payments_present_renders_risk_metrics(self) -> None:
        verdict = PaymentVerdict(_stats(payment_count=10, p50_risk=42.5, p90_risk=78.9))
        html = _render(verdict)
        assert "P50 Risk Score" in html
        assert "P90 Risk Score" in html
        assert "42.5" in html
        assert "78.9" in html


class TestBalanceColor:
    def test_negative_transfer_sum_renders_red(self) -> None:
        # Pin: red cue for in-the-red balance. Drift to flip
        # would invert the financial-state cue moderators rely
        # on.
        verdict = PaymentVerdict(_stats(transfer_sum=-1000))
        html = _render(verdict)
        assert "text-red-600" in html

    def test_zero_transfer_sum_renders_green(self) -> None:
        # Pin: ``>= 0`` is green (zero is "in good standing",
        # not "negative"). Drift to strict ``> 0`` would mis-
        # flag fresh workspaces with no settled balance yet.
        verdict = PaymentVerdict(_stats(transfer_sum=0))
        html = _render(verdict)
        assert "text-green-600" in html

    def test_positive_transfer_sum_renders_green(self) -> None:
        verdict = PaymentVerdict(_stats(transfer_sum=10_000))
        html = _render(verdict)
        assert "text-green-600" in html


class TestP90HighlightAtRedThreshold:
    def test_p90_below_75_is_not_highlighted(self) -> None:
        # Pin: only P90 ``>= 75`` highlights the row. Drift to a
        # different threshold here would visually mis-flag in
        # this component (out of sync with the
        # ``determine_risk_level`` red bound).
        verdict = PaymentVerdict(_stats(payment_count=1, p90_risk=74.99))
        html = _render(verdict)
        # The blue highlight class is present only when
        # highlight=True — absence of the highlight bg is the pin.
        assert "bg-blue-50" not in html

    def test_p90_at_75_is_highlighted(self) -> None:
        verdict = PaymentVerdict(_stats(payment_count=1, p90_risk=75.0))
        html = _render(verdict)
        assert "bg-blue-50" in html


class TestActionsGate:
    def test_no_actions_when_show_actions_false(self) -> None:
        # Pin: actions are ONLY emitted when ``show_actions`` AND
        # ``request`` are both set. Drift to bypass the gate
        # would surface destructive buttons on read-only views.
        verdict = PaymentVerdict(
            _stats(payment_count=1),
            workspace=MagicMock(next_review_threshold=0, is_under_review=True),
            show_actions=False,
            request=None,
        )
        html = _render(verdict)
        assert "Approve" not in html
        assert "Deny" not in html
