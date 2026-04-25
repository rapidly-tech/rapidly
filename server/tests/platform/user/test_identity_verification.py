"""Tests for the identity-verification state machine in
``rapidly/platform/user/actions.py``.

Six load-bearing surfaces:

- ``_guard_verification_state`` raises ``IdentityAlreadyVerified``
  when the user is already verified, and ``IdentityVerificationProcessing``
  when they have a pending session. Drift to skip the guard would
  let a verified user start a new Stripe Identity session
  (paying for a duplicate verification) OR step on a pending
  one mid-flight.
- ``identity_verification_verified`` REQUIRES the inbound Stripe
  webhook session to have ``status == "verified"`` — drift to
  trust any status would mark unverified users as verified
  (massive trust escalation).
- ``identity_verification_pending`` is IDEMPOTENT for already-
  verified users (late webhook with ``processing`` status doesn't
  regress them back to pending). Drift would un-verify users
  whose webhooks arrived out of order.
- ``identity_verification_pending`` requires status ==
  "processing" for non-verified users.
- ``_transition_verification`` raises
  ``IdentityVerificationDoesNotExist`` when the verification id
  doesn't match a user (defensive — Stripe could send us a
  webhook for a session we never created).
- ``get_by_email_or_create`` returns ``(existing, False)`` for a
  hit and creates + dispatches a signup task for a miss.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from rapidly.models.user import IdentityVerificationStatus
from rapidly.platform.user.actions import (
    IdentityAlreadyVerified,
    IdentityVerificationDoesNotExist,
    IdentityVerificationProcessing,
    _guard_verification_state,
    get_by_email_or_create,
    identity_verification_pending,
    identity_verification_verified,
)


def _user(*, verified: bool = False, status: Any = None) -> Any:
    user = MagicMock()
    user.id = uuid4()
    user.identity_verified = verified
    user.identity_verification_status = status or IdentityVerificationStatus.unverified
    return user


class TestGuardVerificationState:
    def test_raises_when_already_verified(self) -> None:
        # Pin: a verified user cannot start a new Stripe Identity
        # session. Drift would charge for duplicate verifications.
        with pytest.raises(IdentityAlreadyVerified):
            _guard_verification_state(_user(verified=True))

    def test_raises_when_pending(self) -> None:
        # Pin: a pending session must complete (or fail) before
        # the user can start another. Drift would step on the
        # in-flight session AND allocate a second Stripe-side
        # verification.
        with pytest.raises(IdentityVerificationProcessing):
            _guard_verification_state(
                _user(verified=False, status=IdentityVerificationStatus.pending)
            )

    def test_passes_for_unverified_with_no_pending(self) -> None:
        # Pin: clean path doesn't raise.
        _guard_verification_state(
            _user(verified=False, status=IdentityVerificationStatus.unverified)
        )

    def test_passes_for_failed_state(self) -> None:
        # Pin: a previously-failed session is allowed to be retried.
        _guard_verification_state(
            _user(verified=False, status=IdentityVerificationStatus.failed)
        )


@pytest.mark.asyncio
class TestIdentityVerificationVerified:
    async def test_rejects_non_verified_status(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Pin: drift to trust any status would let an attacker
        # who can forge a webhook mark unverified users as
        # verified — a massive trust escalation.
        vs = MagicMock()
        vs.id = "vs_test"
        vs.status = "requires_input"

        with pytest.raises(ValueError, match="Expected verified status"):
            await identity_verification_verified(MagicMock(), vs)

    async def test_promotes_user_to_verified(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Pin: clean path → repo.update with status=verified.
        user = _user()
        repo = MagicMock()
        repo.get_by_identity_verification_id = AsyncMock(return_value=user)
        repo.update = AsyncMock(return_value=user)

        monkeypatch.setattr(
            "rapidly.platform.user.actions.UserRepository.from_session",
            MagicMock(return_value=repo),
        )

        vs = MagicMock()
        vs.id = "vs_test"
        vs.status = "verified"

        await identity_verification_verified(MagicMock(), vs)

        repo.update.assert_called_once_with(
            user,
            update_dict={
                "identity_verification_status": IdentityVerificationStatus.verified
            },
        )


@pytest.mark.asyncio
class TestIdentityVerificationPending:
    async def test_already_verified_users_not_regressed(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Pin: a late "processing" webhook for an already-verified
        # user MUST NOT regress them. Drift would un-verify users
        # whose webhooks arrived out of order.
        user = _user(verified=True)
        repo = MagicMock()
        repo.get_by_identity_verification_id = AsyncMock(return_value=user)
        repo.update = AsyncMock()

        monkeypatch.setattr(
            "rapidly.platform.user.actions.UserRepository.from_session",
            MagicMock(return_value=repo),
        )

        vs = MagicMock()
        vs.id = "vs_test"
        vs.status = "processing"

        result = await identity_verification_pending(MagicMock(), vs)

        # Returns the user unchanged, no update applied.
        assert result is user
        repo.update.assert_not_called()

    async def test_rejects_non_processing_status_for_unverified(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Pin: status MUST be "processing" — drift would silently
        # update the user on whatever Stripe sends.
        user = _user(verified=False)
        repo = MagicMock()
        repo.get_by_identity_verification_id = AsyncMock(return_value=user)

        monkeypatch.setattr(
            "rapidly.platform.user.actions.UserRepository.from_session",
            MagicMock(return_value=repo),
        )

        vs = MagicMock()
        vs.id = "vs_test"
        vs.status = "requires_input"

        with pytest.raises(ValueError, match="Expected processing status"):
            await identity_verification_pending(MagicMock(), vs)

    async def test_processing_status_marks_pending(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        user = _user(verified=False)
        repo = MagicMock()
        repo.get_by_identity_verification_id = AsyncMock(return_value=user)
        repo.update = AsyncMock(return_value=user)

        monkeypatch.setattr(
            "rapidly.platform.user.actions.UserRepository.from_session",
            MagicMock(return_value=repo),
        )

        vs = MagicMock()
        vs.id = "vs_test"
        vs.status = "processing"

        await identity_verification_pending(MagicMock(), vs)

        repo.update.assert_called_once_with(
            user,
            update_dict={
                "identity_verification_status": IdentityVerificationStatus.pending
            },
        )


@pytest.mark.asyncio
class TestUnknownVerificationId:
    async def test_raises_when_no_user_matches(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Pin: defensive — Stripe could send us a webhook for a
        # session we never created (test env, replayed event,
        # bad webhook secret). Drift to silently accept would
        # crash later or update the wrong user.
        repo = MagicMock()
        repo.get_by_identity_verification_id = AsyncMock(return_value=None)

        monkeypatch.setattr(
            "rapidly.platform.user.actions.UserRepository.from_session",
            MagicMock(return_value=repo),
        )

        vs = MagicMock()
        vs.id = "vs_unknown"
        vs.status = "verified"

        with pytest.raises(IdentityVerificationDoesNotExist):
            await identity_verification_verified(MagicMock(), vs)


@pytest.mark.asyncio
class TestGetByEmailOrCreate:
    async def test_existing_user_returns_false_flag(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Pin: ``(user, False)`` for an existing user — no
        # signup task dispatched.
        existing = _user()
        repo = MagicMock()
        repo.get_by_email = AsyncMock(return_value=existing)

        monkeypatch.setattr(
            "rapidly.platform.user.actions.UserRepository.from_session",
            MagicMock(return_value=repo),
        )
        dispatch_mock = MagicMock()
        monkeypatch.setattr(
            "rapidly.platform.user.actions.dispatch_task", dispatch_mock
        )

        user, created = await get_by_email_or_create(MagicMock(), "alice@example.com")

        assert user is existing
        assert created is False
        dispatch_mock.assert_not_called()

    async def test_missing_user_creates_and_dispatches_signup_task(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Pin: new-user path → repo.create + dispatch
        # ``user.on_after_signup``. Drift to skip the dispatch
        # would silently fail post-signup orchestration (welcome
        # email, analytics event).
        repo = MagicMock()
        repo.get_by_email = AsyncMock(return_value=None)
        new_user = _user()
        repo.create = AsyncMock(return_value=new_user)

        monkeypatch.setattr(
            "rapidly.platform.user.actions.UserRepository.from_session",
            MagicMock(return_value=repo),
        )
        dispatch_mock = MagicMock()
        monkeypatch.setattr(
            "rapidly.platform.user.actions.dispatch_task", dispatch_mock
        )

        user, created = await get_by_email_or_create(MagicMock(), "fresh@example.com")

        assert user is new_user
        assert created is True
        dispatch_mock.assert_called_once_with(
            "user.on_after_signup", user_id=new_user.id
        )
