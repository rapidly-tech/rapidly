"""Schemas for workspace admin panel components."""

from dataclasses import dataclass


@dataclass(frozen=True)
class PaymentStatistics:
    """Payment statistics for workspace account review."""

    payment_count: int
    p50_risk: float
    p90_risk: float
    transfer_sum: int
    total_payment_amount: int


@dataclass(frozen=True)
class SetupVerdictData:
    """Setup verdict data for workspace integration status."""

    webhooks_count: int
    api_keys_count: int
    products_count: int
    user_verified: bool
    account_charges_enabled: bool
    account_payouts_enabled: bool
    setup_score: int
    webhooks_configured: bool
    products_configured: bool
    api_keys_created: bool
