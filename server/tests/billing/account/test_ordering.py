"""Tests for ``rapidly/billing/account/ordering.py``."""

from __future__ import annotations

from rapidly.billing.account.ordering import AccountSortProperty


class TestAccountSortProperty:
    def test_contains_only_created_at(self) -> None:
        # Minimal surface — the payout-account list is small enough
        # that timestamp is the only meaningful sort column.
        assert {e.value for e in AccountSortProperty} == {"created_at"}

    def test_is_str_enum(self) -> None:
        assert str(AccountSortProperty.created_at) == "created_at"
