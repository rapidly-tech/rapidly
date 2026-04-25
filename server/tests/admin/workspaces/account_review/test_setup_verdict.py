"""Tests for ``rapidly/admin/workspaces/account_review/_setup_verdict.py``.

Five load-bearing surfaces:

- ``_get_logfire_url`` builds the deep-link to Logfire's API-log
  search filtered to the workspace's ``subject_id`` for the last
  30 days. Drift to drop the workspace filter would dump the
  GLOBAL log stream into the moderator's link — a privacy / DDoS
  hazard.
- ``_get_logfire_url`` uses ``urllib.parse.urlencode`` so values
  containing single quotes / spaces are correctly escaped. Drift
  to f-string would let an attacker-controlled UUID (it can't,
  it's a UUID, but the defence-in-depth pattern matters) break
  out of the query string.
- ``_render_detail_item`` colours the dot ``bg-green-500`` for
  truthy ``status`` and ``bg-red-500`` for falsy. Drift would
  invert the moderator's at-a-glance signal.
- The "Account Charges & Payouts Enabled" row goes green ONLY
  when BOTH ``charges_enabled`` AND ``payouts_enabled`` are true
  (drift to OR would mark partially-onboarded accounts as
  fully-set-up).
- The Logfire link section ONLY renders when ``workspace`` is
  truthy — drift to default-render would crash on the empty
  state with ``AttributeError`` on ``.id``.
"""

from __future__ import annotations

from unittest.mock import MagicMock
from uuid import UUID

from tagflow import document

from rapidly.admin.workspaces.account_review._setup_verdict import (
    SetupVerdict,
    _get_logfire_url,
)
from rapidly.admin.workspaces.types import SetupVerdictData


def _data(
    *,
    webhooks_count: int = 0,
    api_keys_count: int = 0,
    products_count: int = 0,
    user_verified: bool = False,
    account_charges_enabled: bool = False,
    account_payouts_enabled: bool = False,
) -> SetupVerdictData:
    return SetupVerdictData(
        webhooks_count=webhooks_count,
        api_keys_count=api_keys_count,
        products_count=products_count,
        user_verified=user_verified,
        account_charges_enabled=account_charges_enabled,
        account_payouts_enabled=account_payouts_enabled,
        setup_score=0,
        webhooks_configured=webhooks_count > 0,
        products_configured=products_count > 0,
        api_keys_created=api_keys_count > 0,
    )


def _render(verdict: SetupVerdict) -> str:
    with document() as doc:
        with verdict.render():
            pass
    return doc.to_html()


class TestLogfireUrl:
    def test_includes_workspace_id_filter(self) -> None:
        # Pin: the deep link narrows logs to ONE workspace via
        # ``subject_id``. Drift to drop the filter would dump
        # the global production log stream into the moderator's
        # browser tab.
        wid = UUID("11111111-1111-1111-1111-111111111111")
        url = _get_logfire_url(wid)
        assert str(wid) in url

    def test_thirty_day_window_pinned(self) -> None:
        # Pin: 30-day window. Drift to a wider window would
        # spike the upstream Logfire query cost; drift to
        # narrower would miss the long-tail signal moderators
        # need for review.
        url = _get_logfire_url(UUID("11111111-1111-1111-1111-111111111111"))
        assert "last=30d" in url

    def test_uses_urlencoded_query_string(self) -> None:
        # Pin: ``urllib.parse.urlencode`` escapes spaces and
        # quotes. The single-quote characters around the UUID
        # in the ``q=`` value MUST be percent-encoded. Drift to
        # f-string concat would emit raw ``'`` and break the
        # link in URL-bar copy-paste.
        url = _get_logfire_url(UUID("11111111-1111-1111-1111-111111111111"))
        # Single quotes are encoded as %27.
        assert "%27" in url
        assert "https://logfire-us.pydantic.dev/" in url


class TestRenderStatusDots:
    def test_zero_count_renders_red_dot(self) -> None:
        # Pin: empty signals (no webhooks / no keys / no
        # products) get ``bg-red-500`` so the moderator
        # immediately sees what's missing.
        verdict = SetupVerdict(_data())
        html = _render(verdict)
        assert "bg-red-500" in html

    def test_nonzero_count_renders_green_dot(self) -> None:
        verdict = SetupVerdict(
            _data(webhooks_count=1, api_keys_count=1, products_count=1)
        )
        html = _render(verdict)
        assert "bg-green-500" in html


class TestAccountChargesAndPayoutsBothRequired:
    def test_only_charges_enabled_renders_red(self) -> None:
        # Pin: AND-gated. Drift to OR would mark partially-
        # onboarded accounts (charges-only, payouts incomplete)
        # as fully-set-up in the moderator's view.
        verdict = SetupVerdict(
            _data(account_charges_enabled=True, account_payouts_enabled=False)
        )
        html = _render(verdict)
        # The "Account Charges & Payouts Enabled" row must show
        # the red dot indicator.
        assert "Account Charges &amp; Payouts Enabled" in html
        # At least one red dot present (the user-verified row
        # also red); the AND-gate test covers both.
        assert "bg-red-500" in html

    def test_only_payouts_enabled_renders_red(self) -> None:
        verdict = SetupVerdict(
            _data(account_charges_enabled=False, account_payouts_enabled=True)
        )
        html = _render(verdict)
        assert "bg-red-500" in html

    def test_both_enabled_renders_green(self) -> None:
        # Pin: when BOTH flags are true AND user is verified,
        # at-a-glance the moderator sees no red dots in the
        # verification section.
        verdict = SetupVerdict(
            _data(
                account_charges_enabled=True,
                account_payouts_enabled=True,
                user_verified=True,
                webhooks_count=1,
                api_keys_count=1,
                products_count=1,
            )
        )
        html = _render(verdict)
        assert "bg-green-500" in html
        # No red dots — every signal is green.
        assert "bg-red-500" not in html


class TestLogfireLinkGate:
    def test_no_workspace_no_logfire_link(self) -> None:
        # Pin: the Logfire link only renders when ``workspace``
        # is truthy. Drift to default-render would crash on the
        # empty state when listing freshly-created workspaces
        # without a model bound.
        verdict = SetupVerdict(_data(), workspace=None)
        html = _render(verdict)
        assert "logfire-us.pydantic.dev" not in html
        assert "View API Logs" not in html

    def test_workspace_present_renders_logfire_link(self) -> None:
        wid = UUID("22222222-2222-2222-2222-222222222222")
        workspace = MagicMock()
        workspace.id = wid
        verdict = SetupVerdict(_data(), workspace=workspace)
        html = _render(verdict)
        assert "View API Logs in Logfire" in html
        # The deep link to Logfire must point at THIS workspace.
        assert str(wid) in html

    def test_logfire_link_opens_new_tab_safely(self) -> None:
        # Pin: ``target=_blank`` + ``rel=noopener noreferrer``.
        # Drift to drop ``noopener`` opens the moderator to a
        # tab-nabbing attack from a malicious Logfire response;
        # drift to drop ``noreferrer`` leaks the admin URL into
        # Logfire's referrer logs.
        workspace = MagicMock()
        workspace.id = UUID("33333333-3333-3333-3333-333333333333")
        verdict = SetupVerdict(_data(), workspace=workspace)
        html = _render(verdict)
        assert "noopener" in html
        assert "noreferrer" in html
        assert 'target="_blank"' in html
