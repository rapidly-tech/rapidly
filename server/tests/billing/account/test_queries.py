"""Tests for ``rapidly/billing/account/queries.py``.

Five load-bearing surfaces:

- ``clear_stripe_fields`` resets ALL FOUR documented Stripe-
  derived flags (``stripe_id``, ``is_details_submitted``,
  ``is_charges_enabled``, ``is_payouts_enabled``). Drift to
  drop a flag would leave a disconnected account looking like
  it could still charge / receive payouts.
- ``clear_stripe_id`` resets ONLY ``stripe_id`` (used by the
  reconnect flow that wants to keep the historical
  charges/payouts flags). Drift to also-clear-flags would
  reset the audit trail on a benign reconnect.
- ``update_stripe_data`` only writes fields the caller passes
  (None-skip semantics). Drift to set-all would null out
  fields the Stripe webhook payload didn't include.
- ``get_readable_statement``: USER → ``admin_id == user_id``
  scope; WORKSPACE → ``false()`` literal so workspace tokens
  CANNOT enumerate accounts (drift would let a workspace token
  see every account in the system).
- Owner-resolution methods (``get_by_user`` / ``get_by_workspace``)
  JOIN the right tables on the right FK columns — drift would
  silently mis-resolve to a different account.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from rapidly.billing.account.queries import AccountRepository


def _compile(stmt: object) -> str:
    return str(stmt.compile(compile_kwargs={"literal_binds": True}))  # type: ignore[attr-defined]


@pytest.mark.asyncio
class TestClearStripeFields:
    async def test_resets_all_four_documented_flags(self) -> None:
        # Pin: drift to drop a flag would leave a disconnected
        # account still looking like it can charge / payout.
        repo = AccountRepository(session=MagicMock())
        captured: dict[str, Any] = {}

        async def _update(obj: Any, update_dict: dict[str, Any]) -> Any:
            captured["update_dict"] = update_dict
            return obj

        repo.update = AsyncMock(side_effect=_update)  # type: ignore[method-assign]

        await repo.clear_stripe_fields(MagicMock())

        assert captured["update_dict"] == {
            "stripe_id": None,
            "is_details_submitted": False,
            "is_charges_enabled": False,
            "is_payouts_enabled": False,
        }


@pytest.mark.asyncio
class TestClearStripeId:
    async def test_only_resets_stripe_id_field(self) -> None:
        # Pin: reconnect flow keeps the historical
        # charges/payouts flags intact. Drift to also-clear
        # would reset the audit trail.
        repo = AccountRepository(session=MagicMock())
        captured: dict[str, Any] = {}

        async def _update(obj: Any, update_dict: dict[str, Any]) -> Any:
            captured["update_dict"] = update_dict
            return obj

        repo.update = AsyncMock(side_effect=_update)  # type: ignore[method-assign]

        await repo.clear_stripe_id(MagicMock())

        assert captured["update_dict"] == {"stripe_id": None}


@pytest.mark.asyncio
class TestUpdateStripeData:
    async def test_omits_unspecified_fields(self) -> None:
        # Pin: None-skip semantics. Drift to set-all would null
        # out fields the Stripe webhook payload didn't include
        # (an account.updated webhook with a partial payload
        # would erase fields).
        repo = AccountRepository(session=MagicMock())
        captured: dict[str, Any] = {}

        async def _update(obj: Any, update_dict: dict[str, Any]) -> Any:
            captured["update_dict"] = update_dict
            return obj

        repo.update = AsyncMock(side_effect=_update)  # type: ignore[method-assign]

        await repo.update_stripe_data(
            MagicMock(),
            stripe_id="acct_abc",
            country="US",
        )

        assert captured["update_dict"] == {"stripe_id": "acct_abc", "country": "US"}

    async def test_writes_documented_fields_when_supplied(self) -> None:
        # Pin: every documented kwarg surfaces in the update
        # dict when set. Drift to drop a kwarg would silently
        # ignore Stripe webhook updates for that field.
        repo = AccountRepository(session=MagicMock())
        captured: dict[str, Any] = {}

        async def _update(obj: Any, update_dict: dict[str, Any]) -> Any:
            captured["update_dict"] = update_dict
            return obj

        repo.update = AsyncMock(side_effect=_update)  # type: ignore[method-assign]

        await repo.update_stripe_data(
            MagicMock(),
            stripe_id="acct_abc",
            email="acc@example.com",
            country="US",
            currency="usd",
            is_details_submitted=True,
            is_charges_enabled=True,
            is_payouts_enabled=False,
            business_type="individual",
            data={"foo": "bar"},
        )

        assert captured["update_dict"] == {
            "stripe_id": "acct_abc",
            "email": "acc@example.com",
            "country": "US",
            "currency": "usd",
            "is_details_submitted": True,
            "is_charges_enabled": True,
            "is_payouts_enabled": False,
            "business_type": "individual",
            "data": {"foo": "bar"},
        }

    async def test_explicit_false_is_persisted(self) -> None:
        # Pin: ``is_payouts_enabled=False`` is a meaningful
        # transition (drift to skip-falsy would forget to record
        # the disable).
        repo = AccountRepository(session=MagicMock())
        captured: dict[str, Any] = {}

        async def _update(obj: Any, update_dict: dict[str, Any]) -> Any:
            captured["update_dict"] = update_dict
            return obj

        repo.update = AsyncMock(side_effect=_update)  # type: ignore[method-assign]

        await repo.update_stripe_data(MagicMock(), is_charges_enabled=False)

        assert captured["update_dict"] == {"is_charges_enabled": False}


class TestGetReadableStatement:
    def test_user_principal_scoped_to_admin_id(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Pin: USER → only accounts where they're the admin.
        # Drift to drop would let any user enumerate every
        # account.
        repo = AccountRepository(session=MagicMock())

        principal = MagicMock()
        principal.subject = MagicMock()
        target = uuid4()
        principal.subject.id = target

        monkeypatch.setattr(
            "rapidly.billing.account.queries.is_user_principal",
            lambda p: True,
        )
        monkeypatch.setattr(
            "rapidly.billing.account.queries.is_workspace_principal",
            lambda p: False,
        )

        stmt = repo.get_readable_statement(principal)
        sql = _compile(stmt).lower()
        assert "accounts.admin_id" in sql
        assert target.hex in sql.replace("-", "")

    def test_workspace_principal_filters_to_false(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Pin: workspace tokens MUST NOT enumerate accounts.
        # The implementation pins this with a literal ``false()``
        # WHERE clause. Drift would let a workspace token see
        # every payout account in the system.
        repo = AccountRepository(session=MagicMock())

        principal = MagicMock()
        monkeypatch.setattr(
            "rapidly.billing.account.queries.is_user_principal",
            lambda p: False,
        )
        monkeypatch.setattr(
            "rapidly.billing.account.queries.is_workspace_principal",
            lambda p: True,
        )

        stmt = repo.get_readable_statement(principal)
        sql = _compile(stmt).lower()
        # The literal ``false`` constant is rendered as ``false``
        # in the WHERE clause.
        assert "false" in sql


@pytest.mark.asyncio
class TestOwnerResolution:
    async def test_get_by_user_joins_users_on_account_id(self) -> None:
        # Pin: JOIN goes ``users.account_id == accounts.id`` (NOT
        # the reverse direction).
        repo = AccountRepository(session=MagicMock())
        captured: dict[str, Any] = {}

        async def _capture(stmt: object) -> Any:
            captured["stmt"] = stmt
            return None

        repo.get_one_or_none = AsyncMock(side_effect=_capture)  # type: ignore[method-assign]

        target = uuid4()
        await repo.get_by_user(target)

        sql = _compile(captured["stmt"]).lower()
        assert "join users" in sql
        assert "users.account_id = accounts.id" in sql
        assert target.hex in sql.replace("-", "")

    async def test_get_by_workspace_joins_workspaces_on_account_id(self) -> None:
        repo = AccountRepository(session=MagicMock())
        captured: dict[str, Any] = {}

        async def _capture(stmt: object) -> Any:
            captured["stmt"] = stmt
            return None

        repo.get_one_or_none = AsyncMock(side_effect=_capture)  # type: ignore[method-assign]

        target = uuid4()
        await repo.get_by_workspace(target)

        sql = _compile(captured["stmt"]).lower()
        assert "join workspaces" in sql
        assert "workspaces.account_id = accounts.id" in sql
        assert target.hex in sql.replace("-", "")
