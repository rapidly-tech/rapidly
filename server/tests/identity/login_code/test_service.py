"""Tests for login code generation and verification."""

import datetime

import pytest
from pytest_mock import MockerFixture
from sqlalchemy import select

from rapidly.core.utils import now_utc
from rapidly.identity.login_code import actions as login_code_service
from rapidly.identity.login_code.actions import LoginCodeInvalidOrExpired
from rapidly.models import LoginCode
from rapidly.postgres import AsyncSession
from tests.fixtures.database import SaveFixture
from tests.fixtures.random_objects import create_user

APP_REVIEW_TEST_EMAIL = "review@test.com"
APP_REVIEW_TEST_CODE_VALID = "TEST01"
APP_REVIEW_TEST_CODE_INVALID = "INVALID"


@pytest.mark.asyncio
class TestAuthenticate:
    async def test_invalid_code(
        self,
        session: AsyncSession,
    ) -> None:
        """Test that authentication fails with an invalid code."""
        with pytest.raises(LoginCodeInvalidOrExpired):
            await login_code_service.authenticate(
                session,
                code=APP_REVIEW_TEST_CODE_INVALID,
                email=APP_REVIEW_TEST_EMAIL,
            )

    async def test_app_review_bypass_disabled_by_default(
        self,
        session: AsyncSession,
    ) -> None:
        """Test that app review bypass doesn't work when not configured."""
        with pytest.raises(LoginCodeInvalidOrExpired):
            await login_code_service.authenticate(
                session,
                code=APP_REVIEW_TEST_CODE_VALID,
                email=APP_REVIEW_TEST_EMAIL,
            )

    async def test_app_review_bypass_works_when_configured(
        self,
        mocker: MockerFixture,
        save_fixture: SaveFixture,
        session: AsyncSession,
    ) -> None:
        """Test that app review bypass works when properly configured."""
        existing_user = await create_user(save_fixture)
        existing_user.email = APP_REVIEW_TEST_EMAIL
        existing_user.email_verified = True
        await save_fixture(existing_user)

        mocker.patch(
            "rapidly.identity.login_code.actions.settings.APP_REVIEW_EMAIL",
            APP_REVIEW_TEST_EMAIL,
        )
        mocker.patch(
            "rapidly.identity.login_code.actions.settings.APP_REVIEW_OTP_CODE",
            APP_REVIEW_TEST_CODE_VALID,
        )

        user, is_signup = await login_code_service.authenticate(
            session,
            code=APP_REVIEW_TEST_CODE_VALID,
            email=APP_REVIEW_TEST_EMAIL,
        )

        assert user is not None
        assert user.id == existing_user.id
        assert user.email == APP_REVIEW_TEST_EMAIL

    async def test_app_review_bypass_wrong_code(
        self,
        mocker: MockerFixture,
        session: AsyncSession,
    ) -> None:
        """Test that app review bypass fails with wrong code."""
        mocker.patch(
            "rapidly.identity.login_code.actions.settings.APP_REVIEW_EMAIL",
            APP_REVIEW_TEST_EMAIL,
        )
        mocker.patch(
            "rapidly.identity.login_code.actions.settings.APP_REVIEW_OTP_CODE",
            APP_REVIEW_TEST_CODE_VALID,
        )

        with pytest.raises(LoginCodeInvalidOrExpired):
            await login_code_service.authenticate(
                session,
                code="WRONG1",
                email=APP_REVIEW_TEST_EMAIL,
            )

    async def test_app_review_bypass_wrong_email(
        self,
        mocker: MockerFixture,
        session: AsyncSession,
    ) -> None:
        """Test that app review bypass fails with wrong email."""
        mocker.patch(
            "rapidly.identity.login_code.actions.settings.APP_REVIEW_EMAIL",
            APP_REVIEW_TEST_EMAIL,
        )
        mocker.patch(
            "rapidly.identity.login_code.actions.settings.APP_REVIEW_OTP_CODE",
            APP_REVIEW_TEST_CODE_VALID,
        )

        with pytest.raises(LoginCodeInvalidOrExpired):
            await login_code_service.authenticate(
                session,
                code=APP_REVIEW_TEST_CODE_VALID,
                email="wrong@example.com",
            )

    async def test_app_review_bypass_reuses_existing_user(
        self,
        mocker: MockerFixture,
        save_fixture: SaveFixture,
        session: AsyncSession,
    ) -> None:
        """Test that app review bypass returns existing user if already exists."""
        existing_user = await create_user(save_fixture)
        existing_user.email = APP_REVIEW_TEST_EMAIL
        existing_user.email_verified = True
        await save_fixture(existing_user)

        mocker.patch(
            "rapidly.identity.login_code.actions.settings.APP_REVIEW_EMAIL",
            APP_REVIEW_TEST_EMAIL,
        )
        mocker.patch(
            "rapidly.identity.login_code.actions.settings.APP_REVIEW_OTP_CODE",
            APP_REVIEW_TEST_CODE_VALID,
        )

        user, is_signup = await login_code_service.authenticate(
            session,
            code=APP_REVIEW_TEST_CODE_VALID,
            email=APP_REVIEW_TEST_EMAIL,
        )

        assert user is not None
        assert user.id == existing_user.id
        assert is_signup is False


@pytest.mark.asyncio
class TestRequestPrivacyHygiene:
    """The ``request`` action MUST NOT reveal whether a user
    exists. The login form is anonymous-callable — a return
    code or behaviour that differs between "this email is
    registered" and "this email is unknown" would let an
    attacker enumerate the user database one email at a time.

    These tests pin the current privacy property so a future
    refactor that, say, returns 404 for missing users (or
    skips the LoginCode row creation) fails loudly.
    """

    async def test_creates_login_code_for_existing_user(
        self,
        save_fixture: SaveFixture,
        session: AsyncSession,
    ) -> None:
        existing_user = await create_user(save_fixture)
        existing_user.email = "real@example.com"
        await save_fixture(existing_user)

        record, _ = await login_code_service.request(session, "real@example.com")
        assert record.email == "real@example.com"
        # user_id is set so the redemption path can short-circuit
        # to the existing account.
        assert record.user_id == existing_user.id

    async def test_creates_login_code_for_unknown_user_too(
        self,
        session: AsyncSession,
    ) -> None:
        # Critical: the action MUST run end-to-end (create a
        # LoginCode row, return a tuple) even when the email
        # is unknown. Otherwise a side-channel (faster response,
        # different return shape, missing row) leaks existence.
        record, code = await login_code_service.request(session, "ghost@example.com")
        assert record.email == "ghost@example.com"
        # user_id is None on the row — only an existing user
        # would link. The PRIVATE field difference is fine
        # because it's invisible to the caller; the public
        # response is the same shape.
        assert record.user_id is None
        # The returned plaintext code is still issued, so the
        # send-email call later doesn't short-circuit either.
        assert code
        assert len(code) > 0

    async def test_response_shape_identical_either_way(
        self,
        save_fixture: SaveFixture,
        session: AsyncSession,
    ) -> None:
        # The (LoginCode, code) tuple shape is the same whether
        # the user exists or not. A future refactor that
        # returns ``(None, None)`` for unknown emails would
        # leak existence to the API handler — pin that shape
        # explicitly here.
        existing_user = await create_user(save_fixture)
        existing_user.email = "known@example.com"
        await save_fixture(existing_user)

        known_record, known_code = await login_code_service.request(
            session, "known@example.com"
        )
        unknown_record, unknown_code = await login_code_service.request(
            session, "stranger@example.com"
        )

        # Both return a tuple of (LoginCode, str), never None.
        assert known_record is not None
        assert unknown_record is not None
        assert isinstance(known_code, str)
        assert isinstance(unknown_code, str)
        # And the codes are the same length (both pass through
        # the same _generate_code_hash helper).
        assert len(known_code) == len(unknown_code)


@pytest.mark.asyncio
class TestDeleteExpired:
    """Real-DB integration test for the daily cleanup actor.

    Confirms the action wires the queries.delete_expired call
    correctly and only removes rows whose ``expires_at`` is in
    the past — the unredeemed-but-still-valid case must be
    preserved.
    """

    async def test_purges_expired_but_keeps_valid(
        self,
        session: AsyncSession,
    ) -> None:
        now = now_utc()

        # Pre-seed three rows: one freshly-issued (valid), one
        # already-expired by 1 hour, one expiring 1 hour from
        # now (valid).
        valid_recent = LoginCode(
            code_hash="a" * 64,
            email="valid-recent@example.com",
            expires_at=now + datetime.timedelta(minutes=5),
        )
        expired = LoginCode(
            code_hash="b" * 64,
            email="expired@example.com",
            expires_at=now - datetime.timedelta(hours=1),
        )
        valid_future = LoginCode(
            code_hash="c" * 64,
            email="valid-future@example.com",
            expires_at=now + datetime.timedelta(hours=1),
        )
        session.add_all([valid_recent, expired, valid_future])
        await session.flush()

        await login_code_service.delete_expired(session)
        await session.flush()

        remaining = (
            (
                await session.execute(
                    select(LoginCode).where(
                        LoginCode.code_hash.in_(["a" * 64, "b" * 64, "c" * 64])
                    )
                )
            )
            .scalars()
            .all()
        )
        remaining_hashes = {r.code_hash for r in remaining}
        # Only the expired row is gone; both valid rows remain.
        assert "a" * 64 in remaining_hashes
        assert "b" * 64 not in remaining_hashes
        assert "c" * 64 in remaining_hashes
