"""Tests for ``rapidly/sharing/storefront/actions.py``.

Public storefront read-side. Three load-bearing surfaces:

- Customer-name anonymisation: each ``StorefrontCustomer`` is built
  from ``customer.name[0] if customer.name else customer.email[0]``.
  This shows only the first character of the customer's identity
  on the public page — a regression that emitted the full name or
  email would leak PII to every visitor of the workspace's public
  storefront.
- ``get_storefront`` is the single read-side composition: it must
  return ``None`` (NOT raise, NOT return a partial Storefront)
  when the workspace lookup misses, so the public 404 page can
  render. Drift to raising would surface a 500 to anonymous
  visitors.
- Customer pagination is hardcoded to ``PaginationParams(1, 3)``
  — only 3 customer-name avatars on the storefront. Drift up
  amplifies the PII surface (more first-characters published);
  drift down breaks the documented "Joined by ___, ___ and N
  others" copy.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from rapidly.sharing.storefront import actions as M


def _customer(*, name: str | None, email: str = "alice@example.com") -> Any:
    c = MagicMock()
    c.name = name
    c.email = email
    return c


def _workspace(*, id: Any = "ws-1", slug: str = "acme") -> Any:
    ws = MagicMock()
    ws.id = id
    ws.slug = slug
    # Add the attrs Workspace.model_validate() will read.
    ws.name = "ACME"
    return ws


@pytest.mark.asyncio
class TestGetStorefrontWorkspaceMissing:
    async def test_returns_none_when_workspace_lookup_misses(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Pin: a missing workspace returns None so the public 404
        # page can render. Drift to raising would surface a 500
        # to anonymous visitors and leak the existence-check.
        with patch.object(M, "get", AsyncMock(return_value=None)):
            session = MagicMock()
            result = await M.get_storefront(session, "no-such-slug")
        assert result is None


@pytest.mark.asyncio
class TestGetStorefrontComposition:
    async def test_uses_workspace_id_for_file_shares_query(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Pin: the file_shares query MUST receive the *workspace
        # id* resolved from the slug, not the slug itself. Drift
        # would 0-result on every storefront page.
        ws = _workspace()

        list_fs = AsyncMock(return_value=[])
        list_cust = AsyncMock(return_value=([], 0))

        with (
            patch.object(M, "get", AsyncMock(return_value=ws)),
            patch.object(M, "list_public_file_shares", list_fs),
            patch.object(M, "list_customers", list_cust),
            patch("rapidly.sharing.storefront.actions.Storefront") as Storefront_cls,
        ):
            sentinel = MagicMock()
            Storefront_cls.model_validate = MagicMock(return_value=sentinel)
            session = MagicMock()
            result = await M.get_storefront(session, "acme")

        assert result is sentinel
        # Pin the call shape — file_shares lookup uses workspace.id,
        # not the slug.
        list_fs.assert_awaited_once_with(session, ws.id)

    async def test_customer_pagination_is_first_three(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Pin: the storefront shows the first 3 customer avatars.
        # Drift up amplifies the PII surface; drift down breaks
        # the documented copy. Captured as ``PaginationParams(1, 3)``.
        ws = _workspace()
        list_cust = AsyncMock(return_value=([], 0))

        with (
            patch.object(M, "get", AsyncMock(return_value=ws)),
            patch.object(M, "list_public_file_shares", AsyncMock(return_value=[])),
            patch.object(M, "list_customers", list_cust),
            patch("rapidly.sharing.storefront.actions.Storefront") as Storefront_cls,
        ):
            Storefront_cls.model_validate = MagicMock(return_value="x")
            session = MagicMock()
            await M.get_storefront(session, "acme")

        list_cust.assert_awaited_once()
        kwargs = list_cust.call_args.kwargs
        pagination = kwargs["pagination"]
        # ``PaginationParams(page, limit)`` — page 1, limit 3.
        assert pagination.page == 1
        assert pagination.limit == 3

    async def test_secrets_empty_when_redis_omitted(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Pin: when ``redis`` is None (default), secrets list is
        # empty and ``list_paid_secrets`` is NOT called. Otherwise
        # the storefront would crash on the missing redis client.
        ws = _workspace()
        list_paid = AsyncMock(return_value=[])

        captured: dict[str, Any] = {}

        def capture(payload: Any) -> str:
            captured["payload"] = payload
            return "result"

        with (
            patch.object(M, "get", AsyncMock(return_value=ws)),
            patch.object(M, "list_public_file_shares", AsyncMock(return_value=[])),
            patch.object(M, "list_customers", AsyncMock(return_value=([], 0))),
            patch.object(M, "list_paid_secrets", list_paid),
            patch("rapidly.sharing.storefront.actions.Storefront") as Storefront_cls,
        ):
            Storefront_cls.model_validate = MagicMock(side_effect=capture)
            session = MagicMock()
            await M.get_storefront(session, "acme", redis=None)

        list_paid.assert_not_awaited()
        assert captured["payload"]["secrets"] == []

    async def test_secrets_populated_when_redis_provided(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Pin: when redis is provided, ``list_paid_secrets`` is
        # called with the WORKSPACE ID and each result is parsed
        # into a SecretStorefront.
        ws = _workspace()
        raw = [
            {
                "id": "sec-1",
                "uuid": "uuid-1",
                "created_at": "2026-01-01T00:00:00Z",
                "title": "T",
                "price_cents": 500,
                "currency": "usd",
            }
        ]
        list_paid = AsyncMock(return_value=raw)

        captured: dict[str, Any] = {}

        def capture(payload: Any) -> str:
            captured["payload"] = payload
            return "result"

        with (
            patch.object(M, "get", AsyncMock(return_value=ws)),
            patch.object(M, "list_public_file_shares", AsyncMock(return_value=[])),
            patch.object(M, "list_customers", AsyncMock(return_value=([], 0))),
            patch.object(M, "list_paid_secrets", list_paid),
            patch("rapidly.sharing.storefront.actions.Storefront") as Storefront_cls,
        ):
            Storefront_cls.model_validate = MagicMock(side_effect=capture)
            session = MagicMock()
            redis_client = MagicMock()
            await M.get_storefront(session, "acme", redis=redis_client)

        list_paid.assert_awaited_once_with(redis_client, ws.id)
        secrets = captured["payload"]["secrets"]
        assert len(secrets) == 1


@pytest.mark.asyncio
class TestCustomerNameAnonymisation:
    async def test_first_letter_of_name_when_name_present(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Pin: ``customer.name[0]`` — only the first character
        # appears on the public storefront. A regression that
        # emitted the full name (or even the first word) would
        # leak PII to every visitor of the workspace's public
        # page.
        ws = _workspace()
        customers = [
            _customer(name="Alice Smith"),
            _customer(name="Bob Jones"),
        ]

        captured: dict[str, Any] = {}

        def capture(payload: Any) -> str:
            captured["payload"] = payload
            return "result"

        with (
            patch.object(M, "get", AsyncMock(return_value=ws)),
            patch.object(M, "list_public_file_shares", AsyncMock(return_value=[])),
            patch.object(M, "list_customers", AsyncMock(return_value=(customers, 2))),
            patch("rapidly.sharing.storefront.actions.Storefront") as Storefront_cls,
        ):
            Storefront_cls.model_validate = MagicMock(side_effect=capture)
            session = MagicMock()
            await M.get_storefront(session, "acme")

        names = [c.name for c in captured["payload"]["customers"].customers]
        assert names == ["A", "B"]

    async def test_falls_back_to_first_letter_of_email(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Pin: when ``customer.name`` is None / empty, the bridge
        # falls back to ``customer.email[0]``. Drift to using
        # ``customer.id`` or "?" would either expose a UUID or
        # break the avatar UI.
        ws = _workspace()
        # ``name=None`` triggers the fallback.
        customers = [_customer(name=None, email="zoe@example.com")]

        captured: dict[str, Any] = {}

        def capture(payload: Any) -> str:
            captured["payload"] = payload
            return "result"

        with (
            patch.object(M, "get", AsyncMock(return_value=ws)),
            patch.object(M, "list_public_file_shares", AsyncMock(return_value=[])),
            patch.object(M, "list_customers", AsyncMock(return_value=(customers, 1))),
            patch("rapidly.sharing.storefront.actions.Storefront") as Storefront_cls,
        ):
            Storefront_cls.model_validate = MagicMock(side_effect=capture)
            session = MagicMock()
            await M.get_storefront(session, "acme")

        names = [c.name for c in captured["payload"]["customers"].customers]
        assert names == ["z"]

    async def test_total_count_passed_through(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Pin: ``StorefrontCustomers.total`` reflects the FULL
        # customer count (not just the 3-page slice). The "and
        # N others" copy reads from this. Drift to ``len(customers)``
        # would always show "and 0 others" once you exceed 3.
        ws = _workspace()
        customers = [_customer(name="Alice")] * 3  # Page slice.
        # Total reflects the full count behind the slice.
        with (
            patch.object(M, "get", AsyncMock(return_value=ws)),
            patch.object(M, "list_public_file_shares", AsyncMock(return_value=[])),
            patch.object(M, "list_customers", AsyncMock(return_value=(customers, 47))),
            patch("rapidly.sharing.storefront.actions.Storefront") as Storefront_cls,
        ):
            captured: dict[str, Any] = {}
            Storefront_cls.model_validate = MagicMock(
                side_effect=lambda p: captured.setdefault("payload", p) or "x"
            )
            session = MagicMock()
            await M.get_storefront(session, "acme")

        assert captured["payload"]["customers"].total == 47
