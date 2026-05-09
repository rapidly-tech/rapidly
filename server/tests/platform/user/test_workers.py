"""Tests for ``rapidly/platform/user/workers.py``.

Two load-bearing surfaces:

- Exception hierarchy: ``UserDoesNotExist`` extends ``UserTaskError``
  extends ``BackgroundTaskError`` so the worker's retry middleware
  can catch the family at the base. The exception carries the
  user_id for log-based incident triage.
- ``user_on_after_signup`` raises ``UserDoesNotExist`` when the
  user row is missing (defensive — protects against a worker that
  fires before the signup transaction has committed). When the
  user exists, the actor is currently a no-op (workspace creation
  was moved to manual onboarding); a regression that re-introduced
  auto-workspace-creation would surface as a behaviour change here.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from rapidly.errors import BackgroundTaskError
from rapidly.platform.user import workers as M
from rapidly.platform.user.workers import (
    UserDoesNotExist,
    UserTaskError,
    user_on_after_signup,
)


class TestExceptionHierarchy:
    def test_user_task_error_extends_background_task_error(self) -> None:
        # Pin: callers / retry middleware catch on
        # BackgroundTaskError to classify worker faults.
        assert issubclass(UserTaskError, BackgroundTaskError)

    def test_user_does_not_exist_extends_user_task_error(self) -> None:
        assert issubclass(UserDoesNotExist, UserTaskError)


class TestUserDoesNotExist:
    def test_carries_user_id_attribute(self) -> None:
        # Pin: ``user_id`` available as a public attribute so the
        # error handler can log it for incident triage.
        uid = uuid4()
        err = UserDoesNotExist(uid)
        assert err.user_id == uid

    def test_message_includes_user_id(self) -> None:
        # Pin: the user_id appears in ``str(err)`` so log lines
        # carry the identifier even when the structured-log path
        # is unavailable.
        uid = uuid4()
        err = UserDoesNotExist(uid)
        assert str(uid) in str(err)


@pytest.mark.asyncio
class TestUserOnAfterSignup:
    async def _patch_session(
        self,
        monkeypatch: pytest.MonkeyPatch,
        *,
        user: object | None,
    ) -> None:
        # Replace AsyncSessionMaker + UserRepository so the actor
        # body runs without a real DB.
        cm = AsyncMock()
        cm.__aenter__ = AsyncMock(return_value=MagicMock())
        cm.__aexit__ = AsyncMock(return_value=False)
        monkeypatch.setattr(M, "AsyncSessionMaker", lambda: cm)

        repo = MagicMock()
        repo.get_by_id = AsyncMock(return_value=user)
        from_session = MagicMock(return_value=repo)
        repo_cls = MagicMock()
        repo_cls.from_session = from_session
        monkeypatch.setattr(M, "UserRepository", repo_cls)

    async def test_raises_when_user_missing(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Pin: a worker fired with a user_id that doesn't resolve
        # MUST raise UserDoesNotExist (NOT silently no-op). The
        # worker retry budget will surface the error in dashboards
        # and the dead-letter queue.
        await self._patch_session(monkeypatch, user=None)
        uid = uuid4()
        with pytest.raises(UserDoesNotExist) as exc:
            await user_on_after_signup.__wrapped__(user_id=uid)  # type: ignore[attr-defined]
        assert exc.value.user_id == uid

    async def test_returns_none_when_user_exists(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Pin: the actor is currently a no-op when the user is
        # found. Workspace creation was MOVED to manual
        # onboarding (per the in-code comment). Drift to
        # re-introduce auto-workspace-creation would surface a
        # value here other than None.
        await self._patch_session(monkeypatch, user=MagicMock())
        result = await user_on_after_signup.__wrapped__(  # type: ignore[attr-defined]
            user_id=uuid4()
        )
        assert result is None
