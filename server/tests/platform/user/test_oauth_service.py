"""Tests for ``rapidly/platform/user/oauth_service.py``.

OAuth account-linking service. Three load-bearing surfaces:

- Exception hierarchy: ``OAuthAccountNotFound`` and
  ``CannotDisconnectLastAuthMethod`` both extend ``OAuthError``
  extends ``RapidlyError``. The status codes (404 vs 400)
  distinguish "no such platform link" from "can't disconnect"
  and the frontend renders different remediation copy.
- ``disconnect_platform`` raises ``OAuthAccountNotFound`` when no
  rows match the platform — drift would silently no-op and let
  the frontend show "disconnected!" while the rows remain.
- ``disconnect_platform`` raises ``CannotDisconnectLastAuthMethod``
  when the user has no OTHER auth method AND email is unverified
  — security pin: prevents the user from accidentally locking
  themselves out by removing their only sign-in method.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from rapidly.errors import RapidlyError
from rapidly.models.user import OAuthPlatform
from rapidly.platform.user import oauth_service as M
from rapidly.platform.user.oauth_service import (
    CannotDisconnectLastAuthMethod,
    OAuthAccountNotFound,
    OAuthAccountService,
    OAuthError,
    oauth_account_service,
)


class TestExceptionHierarchy:
    def test_oauth_error_extends_rapidly_error(self) -> None:
        assert issubclass(OAuthError, RapidlyError)

    def test_account_not_found_extends_oauth_error(self) -> None:
        assert issubclass(OAuthAccountNotFound, OAuthError)

    def test_cannot_disconnect_extends_oauth_error(self) -> None:
        assert issubclass(CannotDisconnectLastAuthMethod, OAuthError)


class TestOAuthAccountNotFound:
    def test_status_code_404(self) -> None:
        # Pin: 404 is the documented status for "no such platform
        # link" — frontend's settings page branches on 404 to
        # show "not connected" rather than the disconnect-failed
        # error.
        err = OAuthAccountNotFound(OAuthPlatform.google)
        assert err.status_code == 404

    def test_carries_platform_attribute(self) -> None:
        err = OAuthAccountNotFound(OAuthPlatform.microsoft)
        assert err.platform == OAuthPlatform.microsoft

    def test_message_mentions_platform(self) -> None:
        # Pin: the platform is interpolated for log + user-facing
        # message clarity.
        err = OAuthAccountNotFound(OAuthPlatform.apple)
        assert "apple" in str(err).lower()


class TestCannotDisconnectLastAuthMethod:
    def test_status_code_400(self) -> None:
        # Pin: 400 — different from 404 so the frontend can
        # branch to render the lockout-prevention copy
        # explaining how to re-establish auth before retrying.
        err = CannotDisconnectLastAuthMethod()
        assert err.status_code == 400

    def test_message_explains_remediation(self) -> None:
        # Pin: message tells the user HOW to recover (verify
        # email or connect another OAuth provider).
        err = CannotDisconnectLastAuthMethod()
        msg = str(err)
        assert "verify your email" in msg.lower()
        assert "OAuth" in msg


class TestModuleSingleton:
    def test_oauth_account_service_singleton_exposed(self) -> None:
        # Pin: callers import ``oauth_account_service`` directly.
        # Drift would break every importer.
        assert isinstance(oauth_account_service, OAuthAccountService)


def _user(*, email_verified: bool = False) -> Any:
    user = MagicMock()
    user.id = uuid4()
    user.email_verified = email_verified
    return user


def _oauth_account(*, account_id: str = "acct") -> Any:
    a = MagicMock()
    a.id = uuid4()
    a.account_id = account_id
    return a


@pytest.mark.asyncio
class TestDisconnectPlatform:
    def _setup_repo(
        self,
        monkeypatch: pytest.MonkeyPatch,
        *,
        target_accounts: list[Any],
        remaining: int,
    ) -> Any:
        repo = MagicMock()
        repo.get_all_by_user_and_platform = AsyncMock(return_value=target_accounts)
        repo.count_by_user_excluding = AsyncMock(return_value=remaining)
        repo.delete = AsyncMock()
        repo_cls = MagicMock()
        repo_cls.from_session = MagicMock(return_value=repo)
        monkeypatch.setattr(M, "OAuthAccountRepository", repo_cls)
        return repo

    async def test_raises_account_not_found_when_no_rows(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Pin: empty platform-list → OAuthAccountNotFound. Drift
        # to silently return None would let the frontend show
        # "disconnected!" while no rows were actually deleted.
        self._setup_repo(monkeypatch, target_accounts=[], remaining=99)
        session = AsyncMock()
        with pytest.raises(OAuthAccountNotFound):
            await oauth_account_service.disconnect_platform(
                session, _user(), OAuthPlatform.google
            )

    async def test_raises_last_auth_method_when_no_other_means_and_unverified_email(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Pin (security): if disconnecting would leave the user
        # with NO way to sign in (no other OAuth + unverified
        # email), raise. Otherwise the user could lock themselves
        # out.
        self._setup_repo(monkeypatch, target_accounts=[_oauth_account()], remaining=0)
        session = AsyncMock()
        with pytest.raises(CannotDisconnectLastAuthMethod):
            await oauth_account_service.disconnect_platform(
                session, _user(email_verified=False), OAuthPlatform.google
            )

    async def test_allows_disconnect_when_email_verified_even_with_no_other_oauth(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Pin: a verified email IS itself a sign-in method
        # (login-code flow). So even with no other OAuth
        # accounts, disconnect is allowed when email is verified.
        repo = self._setup_repo(
            monkeypatch, target_accounts=[_oauth_account()], remaining=0
        )
        session = AsyncMock()
        await oauth_account_service.disconnect_platform(
            session, _user(email_verified=True), OAuthPlatform.google
        )
        # Disconnect proceeded — repo.delete was called.
        repo.delete.assert_awaited_once()

    async def test_allows_disconnect_when_other_oauth_remains(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Pin: with another OAuth provider linked, disconnect is
        # safe regardless of email-verification state.
        repo = self._setup_repo(
            monkeypatch,
            target_accounts=[_oauth_account()],
            remaining=2,
        )
        session = AsyncMock()
        await oauth_account_service.disconnect_platform(
            session, _user(email_verified=False), OAuthPlatform.apple
        )
        repo.delete.assert_awaited_once()

    async def test_deletes_all_target_rows_then_flushes(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Pin: ALL rows for the platform are deleted (some users
        # have duplicates from earlier signup races); a single-
        # row delete would leave dangling associations.
        accts = [_oauth_account(), _oauth_account(), _oauth_account()]
        repo = self._setup_repo(monkeypatch, target_accounts=accts, remaining=1)
        session = AsyncMock()
        await oauth_account_service.disconnect_platform(
            session, _user(), OAuthPlatform.google
        )
        assert repo.delete.await_count == 3
        # Pin: ``session.flush`` runs after the deletes so the
        # transaction sees them before the request commits.
        session.flush.assert_awaited_once()
