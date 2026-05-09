"""Tests for ``rapidly/billing/payment_method/queries.py``.

Three load-bearing surfaces:

- ``get_by_customer_and_processor_id`` matches on ALL THREE
  columns (``customer_id`` + ``processor`` + ``processor_id``).
  Drift to drop ``customer_id`` would let an attacker who knows
  ANY processor-side card id (``pm_*``) fetch a payment method
  belonging to a DIFFERENT customer (PII leak / billing-fraud
  vector).
- ``include_deleted=True`` unlocks the soft-deleted lookup
  branch (used during PSP webhook reconciliation when a
  previously-deleted PM reappears). Drift to always-filter
  would 404 the reconciliation; drift to default-include
  would leak deleted methods on regular reads.
- ``list_by_customer`` orders by ``created_at DESC`` (newest-
  first) and scopes by ``customer_id``. Drift to ASC would
  bury the user's most-recent card at the bottom; drift to
  drop the customer scope would leak every customer's
  payment methods through the customer-portal endpoints.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from rapidly.billing.payment_method.queries import PaymentMethodRepository
from rapidly.enums import PaymentProcessor


def _compile(stmt: object) -> str:
    return str(stmt.compile(compile_kwargs={"literal_binds": True}))  # type: ignore[attr-defined]


@pytest.mark.asyncio
class TestGetByCustomerAndProcessorId:
    async def test_filters_by_all_three_columns(self) -> None:
        # Pin: customer_id + processor + processor_id. Drift to
        # drop customer_id would let an attacker who knows ANY
        # ``pm_*`` id fetch another customer's payment method.
        repo = PaymentMethodRepository(session=MagicMock())
        captured: dict[str, Any] = {}

        async def _capture(stmt: object) -> Any:
            captured["stmt"] = stmt
            return None

        repo.get_one_or_none = AsyncMock(side_effect=_capture)  # type: ignore[method-assign]

        customer_id = uuid4()
        await repo.get_by_customer_and_processor_id(
            customer_id, PaymentProcessor.stripe, "pm_abc"
        )

        sql = _compile(captured["stmt"]).lower()
        assert "payment_methods.customer_id" in sql
        assert customer_id.hex in sql.replace("-", "")
        assert "payment_methods.processor" in sql
        assert "'stripe'" in sql
        assert "payment_methods.processor_id" in sql
        assert "'pm_abc'" in sql

    async def test_default_excludes_soft_deleted(self) -> None:
        # Pin: ``include_deleted=False`` (default) gates by
        # ``deleted_at IS NULL`` from get_base_statement.
        repo = PaymentMethodRepository(session=MagicMock())
        captured: dict[str, Any] = {}

        async def _capture(stmt: object) -> Any:
            captured["stmt"] = stmt
            return None

        repo.get_one_or_none = AsyncMock(side_effect=_capture)  # type: ignore[method-assign]
        await repo.get_by_customer_and_processor_id(
            uuid4(), PaymentProcessor.stripe, "pm_abc"
        )

        sql = _compile(captured["stmt"]).lower()
        assert "payment_methods.deleted_at is null" in sql

    async def test_include_deleted_drops_soft_delete_filter(self) -> None:
        # Pin: PSP-webhook reconciliation needs the override
        # (re-attach a previously-deleted PM when Stripe says
        # it's still on the customer). Drift to always-filter
        # would 404 the reconciliation flow.
        repo = PaymentMethodRepository(session=MagicMock())
        captured: dict[str, Any] = {}

        async def _capture(stmt: object) -> Any:
            captured["stmt"] = stmt
            return None

        repo.get_one_or_none = AsyncMock(side_effect=_capture)  # type: ignore[method-assign]
        await repo.get_by_customer_and_processor_id(
            uuid4(),
            PaymentProcessor.stripe,
            "pm_abc",
            include_deleted=True,
        )

        sql = _compile(captured["stmt"]).lower()
        assert "deleted_at is null" not in sql


@pytest.mark.asyncio
class TestListByCustomer:
    async def _captured_stmt(self) -> object:
        repo = PaymentMethodRepository(session=MagicMock())
        captured: dict[str, Any] = {}

        async def _capture(stmt: object) -> list[Any]:
            captured["stmt"] = stmt
            return []

        repo.get_all = AsyncMock(side_effect=_capture)  # type: ignore[method-assign]
        await repo.list_by_customer(uuid4())
        return captured["stmt"]

    async def test_scopes_by_customer_id(self) -> None:
        # Pin: scoped to a single customer. Drift to drop would
        # leak every customer's payment methods to any caller.
        sql = _compile(await self._captured_stmt()).lower()
        assert "payment_methods.customer_id" in sql

    async def test_orders_by_created_at_desc(self) -> None:
        # Pin: newest-first. Drift to ASC would bury the user's
        # most-recently-added card at the bottom of the wallet
        # list.
        sql = _compile(await self._captured_stmt()).lower()
        assert "order by payment_methods.created_at desc" in sql

    async def test_excludes_soft_deleted(self) -> None:
        # Pin: deleted methods don't appear in the wallet list.
        sql = _compile(await self._captured_stmt()).lower()
        assert "payment_methods.deleted_at is null" in sql
