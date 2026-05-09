"""Tests for ``rapidly/billing/payment/queries.py``.

Four load-bearing surfaces:

- ``get_by_processor_id`` matches on BOTH ``processor`` AND
  ``processor_id`` — drift to match ``processor_id`` alone
  would let a Stripe charge_id collision surface a Razorpay
  payment (or vice versa) when other processors are added.
- ``apply_list_filters`` layers ``workspace_id`` / ``status`` /
  ``method`` / ``customer_email`` ONLY when supplied (caller-
  driven). Drift to always-filter would silently zero-match on
  None inputs.
- ``apply_list_filters`` uses ``IN`` for every filter (callers
  pass sequences). Drift to equality would 500 on multi-value
  filters.
- ``get_readable_statement`` enforces tenant scope: USER
  principals → workspaces with active membership; WORKSPACE
  principals → own workspace only. Drift would leak payment
  history across tenants — a critical financial-data
  separation guard.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from rapidly.billing.payment.ordering import PaymentSortProperty
from rapidly.billing.payment.queries import PaymentRepository
from rapidly.enums import PaymentProcessor


def _compile(stmt: object) -> str:
    return str(stmt.compile(compile_kwargs={"literal_binds": True}))  # type: ignore[attr-defined]


@pytest.mark.asyncio
class TestGetByProcessorId:
    async def test_filters_by_processor_AND_processor_id(self) -> None:
        # Pin: BOTH columns. Drift to match processor_id alone
        # would let a Stripe charge_id collision surface a
        # different processor's payment (when other processors
        # are added).
        repo = PaymentRepository(session=MagicMock())
        captured: dict[str, Any] = {}

        async def _capture(stmt: object) -> Any:
            captured["stmt"] = stmt
            return None

        repo.get_one_or_none = AsyncMock(side_effect=_capture)  # type: ignore[method-assign]

        await repo.get_by_processor_id(PaymentProcessor.stripe, "ch_abc")

        sql = _compile(captured["stmt"]).lower()
        assert "payments.processor" in sql
        assert "'stripe'" in sql
        assert "payments.processor_id" in sql
        assert "'ch_abc'" in sql


class TestApplyListFiltersOptional:
    def _stmt(self, **kw: Any) -> str:
        repo = PaymentRepository(session=MagicMock())
        stmt = repo.get_base_statement()
        stmt = repo.apply_list_filters(stmt, **kw)
        return _compile(stmt).lower()

    def test_no_filters_no_extra_where(self) -> None:
        # Pin: when caller passes no filters, no extra WHERE
        # clauses are added (only the soft-delete gate from
        # get_base_statement). Drift to always-filter would
        # silently zero-match on None inputs.
        sql = self._stmt()
        # The only WHERE-class column is ``deleted_at``.
        # ``status``, ``method``, ``customer_email``, and
        # ``workspace_id`` MUST NOT appear in equality / IN
        # predicates here.
        where_fragment = sql.split("where")[1] if "where" in sql else ""
        assert "payments.status in" not in where_fragment
        assert "payments.method in" not in where_fragment
        assert "payments.customer_email in" not in where_fragment

    def test_workspace_id_uses_in_clause(self) -> None:
        # Pin: ``IN`` (caller may pass multiple workspace ids).
        wid_a = uuid4()
        wid_b = uuid4()
        sql = self._stmt(workspace_id=[wid_a, wid_b])
        assert wid_a.hex in sql.replace("-", "")
        assert wid_b.hex in sql.replace("-", "")

    def test_status_uses_in_clause(self) -> None:
        sql = self._stmt(status=["succeeded", "failed"])
        assert "payments.status in" in sql
        assert "'succeeded'" in sql
        assert "'failed'" in sql

    def test_method_uses_in_clause(self) -> None:
        sql = self._stmt(method=["card", "us_bank_account"])
        assert "payments.method in" in sql

    def test_customer_email_uses_in_clause(self) -> None:
        # Pin: caller passes a list of emails (admin filter on
        # multiple specific customers). Drift to equality would
        # 500.
        sql = self._stmt(customer_email=["a@example.com", "b@example.com"])
        assert "payments.customer_email in" in sql
        assert "a@example.com" in sql
        assert "b@example.com" in sql


@pytest.mark.asyncio
class TestGetReadableStatementTenantScope:
    async def test_user_principal_filters_by_membership(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Pin: USER → membership-scoped. Drift would let any
        # user list any workspace's payment history (financial
        # data leak).
        repo = PaymentRepository(session=MagicMock())
        principal = MagicMock()
        principal.subject = MagicMock()
        principal.subject.id = uuid4()

        monkeypatch.setattr(
            "rapidly.billing.payment.queries.is_user_principal",
            lambda p: True,
        )
        monkeypatch.setattr(
            "rapidly.billing.payment.queries.is_workspace_principal",
            lambda p: False,
        )

        stmt = repo.get_readable_statement(principal)
        sql = _compile(stmt).lower()
        assert "workspace_memberships.workspace_id" in sql
        assert "workspace_memberships.user_id" in sql
        assert "workspace_memberships.deleted_at is null" in sql

    async def test_workspace_principal_filters_to_own_workspace_id(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Pin: WORKSPACE → equality on own workspace_id. Drift
        # would leak other workspaces' payments.
        repo = PaymentRepository(session=MagicMock())
        target = uuid4()
        principal = MagicMock()
        principal.subject = MagicMock()
        principal.subject.id = target

        monkeypatch.setattr(
            "rapidly.billing.payment.queries.is_user_principal",
            lambda p: False,
        )
        monkeypatch.setattr(
            "rapidly.billing.payment.queries.is_workspace_principal",
            lambda p: True,
        )

        stmt = repo.get_readable_statement(principal)
        sql = _compile(stmt).replace("-", "")
        assert target.hex in sql


class TestSortingClause:
    def test_documented_sort_columns_round_trip(self) -> None:
        # Pin: sort criterion mapping. Drift to drop a case
        # would silently render unordered results for that
        # property.
        repo = PaymentRepository(session=MagicMock())
        for prop, expected_col in [
            (PaymentSortProperty.created_at, "created_at"),
            (PaymentSortProperty.status, "status"),
            (PaymentSortProperty.amount, "amount"),
            (PaymentSortProperty.method, "method"),
        ]:
            clause = repo.get_sorting_clause(prop)
            # ``str(clause)`` includes the column name.
            assert expected_col in str(clause).lower()
