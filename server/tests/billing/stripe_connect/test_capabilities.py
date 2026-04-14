"""Tests for the per-account presentment currency gate."""

from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest

from rapidly.billing.stripe_connect.capabilities import (
    _compute_supported_currencies,
    get_supported_currencies,
    invalidate_supported_currencies,
)
from rapidly.models.account import Account


def _account(
    *, currency: str, capability_status: str | None, account_id: UUID | None = None
) -> Account:
    """Build a minimal duck-typed account satisfying the compute contract."""
    data: dict[str, Any] = {}
    if capability_status is not None:
        data["capabilities"] = {"card_payments": {"status": capability_status}}
    return cast(
        Account,
        SimpleNamespace(
            id=account_id or uuid4(),
            currency=currency,
            data=data,
        ),
    )


class TestComputeSupportedCurrencies:
    def test_active_us_merchant_accepts_universal_baseline(self) -> None:
        account = _account(currency="usd", capability_status="active")
        assert _compute_supported_currencies(account) == frozenset({"usd", "eur", "gbp"})

    def test_active_uk_merchant_accepts_universal_baseline(self) -> None:
        account = _account(currency="gbp", capability_status="active")
        assert _compute_supported_currencies(account) == frozenset({"usd", "eur", "gbp"})

    def test_active_local_currency_outside_baseline_is_added(self) -> None:
        account = _account(currency="inr", capability_status="active")
        assert _compute_supported_currencies(account) == frozenset(
            {"usd", "eur", "gbp", "inr"}
        )

    def test_pending_capability_returns_empty_set(self) -> None:
        account = _account(currency="usd", capability_status="pending")
        assert _compute_supported_currencies(account) == frozenset()

    def test_pending_capability_accepted_when_flag_enabled(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from rapidly.config import settings

        monkeypatch.setattr(settings, "STRIPE_ACCEPT_PENDING_CAPABILITIES", True)
        account = _account(currency="usd", capability_status="pending")
        assert _compute_supported_currencies(account) == frozenset({"usd", "eur", "gbp"})

    def test_inactive_capability_still_rejected_when_pending_flag_enabled(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from rapidly.config import settings

        monkeypatch.setattr(settings, "STRIPE_ACCEPT_PENDING_CAPABILITIES", True)
        account = _account(currency="usd", capability_status="inactive")
        assert _compute_supported_currencies(account) == frozenset()

    def test_inactive_capability_returns_empty_set(self) -> None:
        account = _account(currency="usd", capability_status="inactive")
        assert _compute_supported_currencies(account) == frozenset()

    def test_missing_capabilities_returns_empty_set(self) -> None:
        account = _account(currency="usd", capability_status=None)
        assert _compute_supported_currencies(account) == frozenset()

    def test_malformed_capability_payload_returns_empty_set(self) -> None:
        account = cast(
            Account,
            SimpleNamespace(
                id=uuid4(),
                currency="usd",
                data={"capabilities": {"card_payments": "active"}},  # wrong shape
            ),
        )
        assert _compute_supported_currencies(account) == frozenset()

    def test_account_currency_is_lowercased(self) -> None:
        account = _account(currency="JPY", capability_status="active")
        assert "jpy" in _compute_supported_currencies(account)


class TestRedisCache:
    @pytest.mark.asyncio
    async def test_cache_miss_computes_and_stores(self) -> None:
        redis = AsyncMock()
        redis.get.return_value = None
        account = _account(currency="usd", capability_status="active")

        result = await get_supported_currencies(redis, account)

        assert result == frozenset({"usd", "eur", "gbp"})
        redis.set.assert_awaited_once()
        key_arg, value_arg = redis.set.await_args.args
        assert key_arg == f"stripe:account:{account.id}:currencies:v1"
        assert set(value_arg.split(",")) == {"usd", "eur", "gbp"}

    @pytest.mark.asyncio
    async def test_cache_hit_returns_cached_value_without_recompute(self) -> None:
        redis = AsyncMock()
        redis.get.return_value = "aud,usd"
        account = _account(currency="usd", capability_status="inactive")  # would compute to empty

        result = await get_supported_currencies(redis, account)

        assert result == frozenset({"aud", "usd"})
        redis.set.assert_not_called()

    @pytest.mark.asyncio
    async def test_cache_hit_empty_string_returns_empty_frozenset(self) -> None:
        redis = AsyncMock()
        redis.get.return_value = ""
        account = _account(currency="usd", capability_status="active")

        result = await get_supported_currencies(redis, account)

        assert result == frozenset()
        redis.set.assert_not_called()

    @pytest.mark.asyncio
    async def test_invalidate_deletes_cache_key(self) -> None:
        redis = AsyncMock()
        account_id = uuid4()

        await invalidate_supported_currencies(redis, account_id)

        redis.delete.assert_awaited_once_with(
            f"stripe:account:{account_id}:currencies:v1"
        )
