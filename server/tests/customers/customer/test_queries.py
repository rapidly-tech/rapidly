"""Tests for ``rapidly/customers/customer/queries.py``.

Five load-bearing surfaces:

- ``_archive_external_id`` moves the customer's ``external_id``
  into ``user_metadata['__external_id']`` on soft delete (so the
  external_id slot can be reused). Drift would orphan
  external_id and prevent new customers from claiming it via
  the merchant's idempotency key.
- ``apply_list_filters`` query searches THREE columns: email +
  name use SUBSTRING (``%q%``); external_id uses PREFIX (``q%``).
  Drift to substring on external_id would surface partial
  matches admins did not intend.
- ``apply_list_filters`` is CASE-INSENSITIVE on email
  (``func.lower(email) == email.lower()``). Drift to bare
  equality would mis-route on case-mixed customer addresses.
- ``apply_list_filters`` escapes user-supplied wildcards via
  ``escape_like`` so a typo'd ``%`` doesn't match every customer.
- ``get_readable_statement``: USER principals → membership-
  scoped (workspace_id IN their active memberships); WORKSPACE
  principals → own workspace only. Drift would leak customers
  across tenants.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from rapidly.customers.customer.ordering import CustomerSortProperty
from rapidly.customers.customer.queries import CustomerRepository


def _compile(stmt: object) -> str:
    return str(stmt.compile(compile_kwargs={"literal_binds": True}))  # type: ignore[attr-defined]


class TestArchiveExternalId:
    def test_moves_external_id_to_metadata_on_soft_delete(self) -> None:
        # Pin: drift would orphan external_id → merchant's
        # next idempotent customer-create with the same id
        # would crash on a unique-key violation that we no
        # longer detect.
        customer = MagicMock()
        customer.external_id = "merchant_id_42"
        customer.user_metadata = {"foo": "bar"}

        CustomerRepository._archive_external_id(customer)

        # The original external_id is now in user_metadata
        # under ``__external_id`` and the column is cleared.
        assert customer.user_metadata["__external_id"] == "merchant_id_42"
        assert customer.user_metadata["foo"] == "bar"
        assert customer.external_id is None

    def test_no_op_when_external_id_is_none(self) -> None:
        customer = MagicMock()
        customer.external_id = None
        customer.user_metadata = {}

        CustomerRepository._archive_external_id(customer)

        # No ``__external_id`` key was created.
        assert "__external_id" not in customer.user_metadata


class TestApplyListFiltersTextSearch:
    def test_query_searches_three_columns(self) -> None:
        # Pin: 3-column search.
        repo = CustomerRepository(session=MagicMock())
        stmt = repo.get_base_statement()
        stmt = repo.apply_list_filters(stmt, query="alice")

        sql = _compile(stmt).lower()
        assert "customers.email" in sql
        assert "customers.name" in sql
        assert "customers.external_id" in sql
        assert " or " in sql

    def test_email_and_name_use_substring(self) -> None:
        # Pin: ``%q%`` for email and name (admins want partial
        # matches on these).
        repo = CustomerRepository(session=MagicMock())
        stmt = repo.get_base_statement()
        stmt = repo.apply_list_filters(stmt, query="alice")

        sql = _compile(stmt)
        # email + name patterns include the leading %.
        assert "%alice%" in sql

    def test_external_id_uses_prefix(self) -> None:
        # Pin: ``q%`` for external_id (admins paste exact
        # merchant ids; substring would surface unrelated rows
        # that happen to contain the substring).
        repo = CustomerRepository(session=MagicMock())
        stmt = repo.get_base_statement()
        stmt = repo.apply_list_filters(stmt, query="m_42")

        sql = _compile(stmt)
        # The external_id pattern is ``m_42%`` (prefix only).
        # Note: ILIKE compiles with both anchors visible.
        # The substring ``m_42%`` appears in the bound literal.
        assert "external_id" in sql.lower()
        # Pattern surfaces exactly once with leading-anchor
        # absent: ``m_42%`` (NOT ``%m_42%``).
        assert "%m_42%" not in sql

    def test_escape_like_applied(self) -> None:
        # Pin: user-supplied ``%`` is escaped (drift would let a
        # typo'd ``%`` match every customer in the workspace).
        repo = CustomerRepository(session=MagicMock())
        stmt = repo.get_base_statement()
        stmt = repo.apply_list_filters(stmt, query="50%off")

        sql = _compile(stmt)
        assert r"50\%off" in sql

    def test_email_filter_is_case_insensitive(self) -> None:
        # Pin: ``func.lower(email) == email.lower()``.
        repo = CustomerRepository(session=MagicMock())
        stmt = repo.get_base_statement()
        stmt = repo.apply_list_filters(stmt, email="Alice@Example.COM")

        sql = _compile(stmt).lower()
        assert "lower(customers.email)" in sql
        assert "alice@example.com" in sql


class TestApplyListFiltersWorkspaceScope:
    def test_workspace_id_filter_is_in_clause(self) -> None:
        # Pin: caller can pass multiple workspace ids; SQL
        # uses ``IN`` (not equality).
        repo = CustomerRepository(session=MagicMock())
        wid_a = uuid4()
        wid_b = uuid4()
        stmt = repo.get_base_statement()
        stmt = repo.apply_list_filters(stmt, workspace_id=[wid_a, wid_b])

        sql = _compile(stmt).replace("-", "")
        assert wid_a.hex in sql
        assert wid_b.hex in sql


class TestApplyListFiltersSorting:
    def test_sort_by_created_at_emits_order_by(self) -> None:
        # Pin: sort criterion mapping. Drift to drop a case
        # would silently render an unordered result for that
        # property.
        repo = CustomerRepository(session=MagicMock())
        stmt = repo.get_base_statement()
        stmt = repo.apply_list_filters(
            stmt,
            sorting=[(CustomerSortProperty.created_at, True)],
        )

        sql = _compile(stmt).lower()
        assert "order by customers.created_at desc" in sql

    def test_sort_by_email_emits_order_by(self) -> None:
        repo = CustomerRepository(session=MagicMock())
        stmt = repo.get_base_statement()
        stmt = repo.apply_list_filters(
            stmt,
            sorting=[(CustomerSortProperty.email, False)],
        )
        sql = _compile(stmt).lower()
        assert "order by customers.email asc" in sql

    def test_sort_by_name_emits_order_by(self) -> None:
        repo = CustomerRepository(session=MagicMock())
        stmt = repo.get_base_statement()
        stmt = repo.apply_list_filters(
            stmt,
            sorting=[(CustomerSortProperty.customer_name, False)],
        )
        sql = _compile(stmt).lower()
        assert "order by customers.name asc" in sql


@pytest.mark.asyncio
class TestGetReadableStatement:
    async def test_user_principal_filters_by_membership(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Pin: USER → workspaces they belong to (active
        # membership). Drift to drop the membership filter
        # would let any user list any workspace's customers.
        repo = CustomerRepository(session=MagicMock())

        principal = MagicMock()
        principal.subject = MagicMock()
        principal.subject.id = uuid4()

        monkeypatch.setattr(
            "rapidly.customers.customer.queries.is_user_principal",
            lambda p: True,
        )
        monkeypatch.setattr(
            "rapidly.customers.customer.queries.is_workspace_principal",
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
        # Pin: WORKSPACE → equality on own workspace_id (no
        # subquery). Drift would leak customers across tenants.
        repo = CustomerRepository(session=MagicMock())

        target = uuid4()
        principal = MagicMock()
        principal.subject = MagicMock()
        principal.subject.id = target

        monkeypatch.setattr(
            "rapidly.customers.customer.queries.is_user_principal",
            lambda p: False,
        )
        monkeypatch.setattr(
            "rapidly.customers.customer.queries.is_workspace_principal",
            lambda p: True,
        )

        stmt = repo.get_readable_statement(principal)
        sql = _compile(stmt).replace("-", "")
        assert target.hex in sql


@pytest.mark.asyncio
class TestGetByEmailAndWorkspaceCaseInsensitive:
    async def test_email_lookup_uses_lower(self) -> None:
        # Pin: case-insensitive on email lookup so a customer
        # registered as ``alice@…`` matches ``Alice@…``.
        repo = CustomerRepository(session=MagicMock())
        captured: dict[str, Any] = {}

        async def _capture(stmt: object) -> Any:
            captured["stmt"] = stmt
            return None

        repo.get_one_or_none = AsyncMock(side_effect=_capture)  # type: ignore[method-assign]
        await repo.get_by_email_and_workspace("Alice@Example.COM", uuid4())

        sql = _compile(captured["stmt"]).lower()
        assert "lower(customers.email)" in sql
        assert "alice@example.com" in sql
