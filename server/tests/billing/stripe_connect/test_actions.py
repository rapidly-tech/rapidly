"""Tests for ``rapidly/billing/stripe_connect/actions.py``.

Five load-bearing surfaces:

- ``_get_stripe_account_id`` raises ``ResourceNotFound`` when the
  workspace isn't readable by the auth subject (privacy guard
  keyed on ``get_readable_statement``). Drift would let a
  caller from another tenant probe Stripe balances.
- ``_get_stripe_account_id`` raises
  ``StripeAccountNotConnected`` when the workspace exists but
  has no ``account_id`` (drift to fall through would NPE deep
  in Stripe SDK calls).
- ``_get_stripe_account_id`` raises
  ``StripeAccountNotConnected`` when the linked account exists
  but has no ``stripe_id`` (drift would surface as opaque
  Stripe error on the dashboard).
- ``get_balance`` propagates ``StripeError`` as
  ``StripeConnectServiceError(status_code=502)`` (drift to let
  the raw error bubble would 500 the dashboard with provider
  internals).
- ``list_payouts`` builds the ``created`` filter dict only when
  ``gte`` / ``lte`` is supplied (drift to always-include would
  emit an empty ``"created": {}`` dict that Stripe rejects).
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
import stripe as stripe_lib

from rapidly.billing.stripe_connect import actions as M
from rapidly.billing.stripe_connect.actions import (
    StripeAccountNotConnected,
    StripeConnectServiceError,
    _get_stripe_account_id,
    get_balance,
    list_payouts,
)
from rapidly.errors import ResourceNotFound


def _make_workspace(*, account_id: Any = None) -> Any:
    workspace = MagicMock()
    workspace.id = uuid4()
    workspace.account_id = account_id
    return workspace


def _make_account(*, stripe_id: str | None = "acct_xyz") -> Any:
    account = MagicMock()
    account.stripe_id = stripe_id
    return account


@pytest.fixture
def patched_repos(monkeypatch: pytest.MonkeyPatch) -> dict[str, MagicMock]:
    """Replace WorkspaceRepository / AccountRepository factories
    with controllable mocks."""
    workspace_repo = MagicMock()
    workspace_repo.get_readable_statement = MagicMock(return_value=MagicMock())
    workspace_repo.get_one_or_none = AsyncMock(return_value=None)

    account_repo = MagicMock()
    account_repo.get_by_id = AsyncMock(return_value=None)

    monkeypatch.setattr(
        "rapidly.billing.stripe_connect.actions.WorkspaceRepository.from_session",
        MagicMock(return_value=workspace_repo),
    )
    monkeypatch.setattr(
        "rapidly.billing.stripe_connect.actions.AccountRepository.from_session",
        MagicMock(return_value=account_repo),
    )
    _ = M
    return {"workspace": workspace_repo, "account": account_repo}


@pytest.mark.asyncio
class TestGetStripeAccountId:
    async def test_unreadable_workspace_raises_resource_not_found(
        self, patched_repos: dict[str, MagicMock]
    ) -> None:
        # Pin: cross-tenant probe → ResourceNotFound (NOT a
        # specific "not connected" error that would leak the
        # workspace's existence).
        patched_repos["workspace"].get_one_or_none.return_value = None

        with pytest.raises(ResourceNotFound):
            await _get_stripe_account_id(MagicMock(), MagicMock(), uuid4())

    async def test_no_account_id_on_workspace_raises_not_connected(
        self, patched_repos: dict[str, MagicMock]
    ) -> None:
        # Pin: distinct from the cross-tenant 404. Drift to fall
        # through would NPE deep in stripe_lib calls.
        workspace = _make_workspace(account_id=None)
        patched_repos["workspace"].get_one_or_none.return_value = workspace

        with pytest.raises(StripeAccountNotConnected):
            await _get_stripe_account_id(MagicMock(), MagicMock(), uuid4())

    async def test_account_without_stripe_id_raises_not_connected(
        self, patched_repos: dict[str, MagicMock]
    ) -> None:
        # Pin: account exists but lacks stripe_id (mid-onboarding
        # state) → not-connected error rather than opaque Stripe
        # error.
        workspace = _make_workspace(account_id=uuid4())
        patched_repos["workspace"].get_one_or_none.return_value = workspace
        patched_repos["account"].get_by_id.return_value = _make_account(stripe_id=None)

        with pytest.raises(StripeAccountNotConnected):
            await _get_stripe_account_id(MagicMock(), MagicMock(), uuid4())

    async def test_returns_stripe_id_when_fully_connected(
        self, patched_repos: dict[str, MagicMock]
    ) -> None:
        workspace = _make_workspace(account_id=uuid4())
        patched_repos["workspace"].get_one_or_none.return_value = workspace
        patched_repos["account"].get_by_id.return_value = _make_account(
            stripe_id="acct_xyz"
        )

        out = await _get_stripe_account_id(MagicMock(), MagicMock(), uuid4())
        assert out == "acct_xyz"


@pytest.mark.asyncio
class TestGetBalanceErrorMapping:
    async def test_stripe_error_maps_to_502_service_error(
        self, monkeypatch: pytest.MonkeyPatch, patched_repos: dict[str, MagicMock]
    ) -> None:
        # Pin: provider errors surface as 502 (Bad Gateway), NOT
        # 500 (which would imply OUR fault) and NOT raw stripe
        # internals leaking to the dashboard.
        workspace = _make_workspace(account_id=uuid4())
        patched_repos["workspace"].get_one_or_none.return_value = workspace
        patched_repos["account"].get_by_id.return_value = _make_account()

        async def _raise(*args: Any, **kwargs: Any) -> None:
            # ``StripeError.user_message`` is a read-only
            # property; create the error and rely on the
            # action's ``user_message or 'Stripe error'`` fallback.
            err = stripe_lib.StripeError("boom")
            raise err

        monkeypatch.setattr(stripe_lib.Balance, "retrieve_async", _raise)

        with pytest.raises(StripeConnectServiceError) as exc:
            await get_balance(MagicMock(), MagicMock(), uuid4())

        assert exc.value.status_code == 502


@pytest.mark.asyncio
class TestListPayoutsParams:
    async def test_omits_created_filter_when_no_dates(
        self, monkeypatch: pytest.MonkeyPatch, patched_repos: dict[str, MagicMock]
    ) -> None:
        # Pin: ``params["created"]`` is NOT set when both bounds
        # are None. Drift to always-add would emit an empty
        # ``{"created": {}}`` that Stripe rejects.
        workspace = _make_workspace(account_id=uuid4())
        patched_repos["workspace"].get_one_or_none.return_value = workspace
        patched_repos["account"].get_by_id.return_value = _make_account()

        captured: dict[str, Any] = {}

        async def _list_async(**params: Any) -> Any:
            captured.update(params)
            result = MagicMock()
            result.data = []
            result.has_more = False
            return result

        monkeypatch.setattr(stripe_lib.Payout, "list_async", _list_async)

        await list_payouts(MagicMock(), MagicMock(), uuid4())

        assert "created" not in captured

    async def test_gte_and_lte_both_packed_into_created_dict(
        self, monkeypatch: pytest.MonkeyPatch, patched_repos: dict[str, MagicMock]
    ) -> None:
        # Pin: both bounds end up under the same ``created`` key.
        # Drift to overwrite would lose one of the bounds.
        workspace = _make_workspace(account_id=uuid4())
        patched_repos["workspace"].get_one_or_none.return_value = workspace
        patched_repos["account"].get_by_id.return_value = _make_account()

        captured: dict[str, Any] = {}

        async def _list_async(**params: Any) -> Any:
            captured.update(params)
            result = MagicMock()
            result.data = []
            result.has_more = False
            return result

        monkeypatch.setattr(stripe_lib.Payout, "list_async", _list_async)

        gte = datetime(2026, 1, 1, tzinfo=UTC)
        lte = datetime(2026, 12, 31, tzinfo=UTC)
        await list_payouts(
            MagicMock(),
            MagicMock(),
            uuid4(),
            created_gte=gte,
            created_lte=lte,
        )

        assert captured["created"] == {
            "gte": int(gte.timestamp()),
            "lte": int(lte.timestamp()),
        }

    async def test_starting_after_forwarded_for_pagination(
        self, monkeypatch: pytest.MonkeyPatch, patched_repos: dict[str, MagicMock]
    ) -> None:
        # Pin: cursor pagination forwards ``starting_after``.
        # Drift to drop would let "load more" silently restart
        # from the top.
        workspace = _make_workspace(account_id=uuid4())
        patched_repos["workspace"].get_one_or_none.return_value = workspace
        patched_repos["account"].get_by_id.return_value = _make_account()

        captured: dict[str, Any] = {}

        async def _list_async(**params: Any) -> Any:
            captured.update(params)
            result = MagicMock()
            result.data = []
            result.has_more = False
            return result

        monkeypatch.setattr(stripe_lib.Payout, "list_async", _list_async)

        await list_payouts(
            MagicMock(),
            MagicMock(),
            uuid4(),
            starting_after="po_abc",
        )

        assert captured["starting_after"] == "po_abc"
