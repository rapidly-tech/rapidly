"""Per-account presentment currency gate for Stripe Connect accounts.

A merchant's connected Stripe account must have ``card_payments`` capability
``active`` before it can accept charges at all, and the presentment currency
must fall within a conservative universal baseline (``usd`` / ``eur`` / ``gbp``)
plus the merchant's own settlement currency. Finer per-country rules can be
layered on later; this baseline is the minimum that avoids silently accepting
a currency the merchant cannot charge in.

Results are cached in Redis and invalidated from the ``account.updated``
webhook so that capability state change propagates within webhook latency
rather than the TTL.
"""

from datetime import timedelta
from typing import Any
from uuid import UUID

from rapidly.config import settings
from rapidly.models.account import Account
from rapidly.redis import Redis

_CACHE_KEY = "stripe:account:{account_id}:currencies:v1"
_CACHE_TTL_SECONDS = int(timedelta(minutes=5).total_seconds())

# Currencies every card_payments-active Stripe account can accept globally.
# See https://docs.stripe.com/currencies — USD/EUR/GBP are the widely
# supported presentment currencies across all Connect account countries.
_UNIVERSAL_PRESENTMENT_CURRENCIES: frozenset[str] = frozenset({"usd", "eur", "gbp"})


def _compute_supported_currencies(account: Account) -> frozenset[str]:
    """Derive the supported-currency set from the stored Stripe account data."""
    capabilities: dict[str, Any] = account.data.get("capabilities", {}) or {}
    card_payments = capabilities.get("card_payments") or {}
    if not isinstance(card_payments, dict):
        return frozenset()

    status = card_payments.get("status")
    accepted = {"active", "pending"} if settings.STRIPE_ACCEPT_PENDING_CAPABILITIES else {"active"}
    if status not in accepted:
        return frozenset()

    supported = set(_UNIVERSAL_PRESENTMENT_CURRENCIES)
    if account.currency:
        supported.add(account.currency.lower())
    return frozenset(supported)


async def get_supported_currencies(
    redis: Redis,
    account: Account,
) -> frozenset[str]:
    """Return the set of presentment currencies this account can accept.

    Empty set means the account cannot accept charges at all (e.g. capability
    inactive). Callers should treat an empty set as a hard-reject signal.
    """
    key = _CACHE_KEY.format(account_id=account.id)
    cached = await redis.get(key)
    if cached is not None:
        return frozenset(cached.split(",")) if cached else frozenset()

    supported = _compute_supported_currencies(account)
    await redis.set(key, ",".join(sorted(supported)), ex=_CACHE_TTL_SECONDS)
    return supported


async def invalidate_supported_currencies(
    redis: Redis,
    account_id: UUID,
) -> None:
    """Evict the cached currency set for an account after a Stripe state change."""
    await redis.delete(_CACHE_KEY.format(account_id=account_id))
