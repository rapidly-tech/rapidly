"""Pydantic schemas for Stripe Connect balance and payout responses."""

from datetime import datetime

from rapidly.core.types import Schema


class StripeBalanceAmount(Schema):
    amount: int
    currency: str


class StripeBalance(Schema):
    available: list[StripeBalanceAmount]
    pending: list[StripeBalanceAmount]


class StripePayout(Schema):
    id: str
    amount: int
    currency: str
    status: str
    arrival_date: datetime
    created: datetime
    description: str | None = None
    method: str


class StripePayoutList(Schema):
    items: list[StripePayout]
    has_more: bool
