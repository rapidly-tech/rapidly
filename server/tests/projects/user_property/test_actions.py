"""Tests for ``rapidly.projects.user_property.actions``.

Invariants pinned:

- ``upsert`` returns 404 (ResourceNotFound) when the project isn't readable
  by the caller — preventing existence-leak via the upsert endpoint.
- ``upsert`` creates a new row with payload data when no row exists.
- ``upsert`` partial-updates an existing row, leaving unmentioned fields alone.
- ``get_mine_for_project`` returns None when nothing has been saved yet.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from rapidly.errors import ResourceNotFound
from rapidly.identity.auth.models import AuthPrincipal
from rapidly.models import ProjectUserProperty, User
from rapidly.projects.user_property import actions as up_actions
from rapidly.projects.user_property.types import ProjectUserPropertyUpsert


def _principal() -> AuthPrincipal[User]:
    return AuthPrincipal(
        subject=User(id=uuid4(), email="dev@example.com"),
        scopes=set(),
        session=None,
    )


def _row(user_id: Any, project_id: Any) -> ProjectUserProperty:
    return ProjectUserProperty(
        id=uuid4(),
        project_id=project_id,
        user_id=user_id,
        filters={},
        display_filters={"order_by": "-created_at"},
        display_properties={},
    )


@pytest.mark.asyncio
class TestUpsert:
    async def test_unreadable_project_rejected(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        principal = _principal()

        async def _no_access(*_a: Any, **_k: Any) -> None:
            raise ResourceNotFound()

        monkeypatch.setattr(
            "rapidly.projects.user_property.actions._ensure_project_readable",
            _no_access,
        )

        with pytest.raises(ResourceNotFound):
            await up_actions.upsert(
                MagicMock(),
                principal,
                ProjectUserPropertyUpsert(project_id=uuid4(), filters={"x": 1}),
            )

    async def test_creates_new_row(self, monkeypatch: pytest.MonkeyPatch) -> None:
        principal = _principal()
        project_id = uuid4()

        async def _ok(*_a: Any, **_k: Any) -> None:
            return None

        monkeypatch.setattr(
            "rapidly.projects.user_property.actions._ensure_project_readable", _ok
        )

        captured: list[Any] = []
        repo = MagicMock()
        repo.get_for_user_and_project = AsyncMock(return_value=None)

        async def _create(obj: Any, flush: bool = False) -> Any:
            captured.append(obj)
            return obj

        repo.create = _create

        with patch(
            "rapidly.projects.user_property.actions.ProjectUserPropertyRepository.from_session",
            return_value=repo,
        ):
            await up_actions.upsert(
                MagicMock(),
                principal,
                ProjectUserPropertyUpsert(
                    project_id=project_id,
                    display_filters={"order_by": "priority"},
                ),
            )

        assert len(captured) == 1
        row = captured[0]
        assert row.project_id == project_id
        assert row.user_id == principal.subject.id
        assert row.display_filters == {"order_by": "priority"}
        # filters and display_properties not in payload → default empty.
        assert row.filters == {}
        assert row.display_properties == {}

    async def test_partial_update_keeps_other_fields(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        principal = _principal()
        existing = _row(principal.subject.id, uuid4())

        async def _ok(*_a: Any, **_k: Any) -> None:
            return None

        monkeypatch.setattr(
            "rapidly.projects.user_property.actions._ensure_project_readable", _ok
        )

        repo = MagicMock()
        repo.get_for_user_and_project = AsyncMock(return_value=existing)
        repo.update = AsyncMock(return_value=existing)

        with patch(
            "rapidly.projects.user_property.actions.ProjectUserPropertyRepository.from_session",
            return_value=repo,
        ):
            await up_actions.upsert(
                MagicMock(),
                principal,
                ProjectUserPropertyUpsert(
                    project_id=existing.project_id,
                    filters={"priority": "high"},
                ),
            )

        assert repo.update.await_count == 1
        _, kwargs = repo.update.call_args
        # Only the field that was explicitly set should land in the update.
        assert kwargs["update_dict"] == {"filters": {"priority": "high"}}

    async def test_empty_payload_is_noop_on_existing(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        principal = _principal()
        existing = _row(principal.subject.id, uuid4())

        async def _ok(*_a: Any, **_k: Any) -> None:
            return None

        monkeypatch.setattr(
            "rapidly.projects.user_property.actions._ensure_project_readable", _ok
        )

        repo = MagicMock()
        repo.get_for_user_and_project = AsyncMock(return_value=existing)
        repo.update = AsyncMock(return_value=existing)

        with patch(
            "rapidly.projects.user_property.actions.ProjectUserPropertyRepository.from_session",
            return_value=repo,
        ):
            result = await up_actions.upsert(
                MagicMock(),
                principal,
                ProjectUserPropertyUpsert(project_id=existing.project_id),
            )

        assert result is existing
        repo.update.assert_not_called()


@pytest.mark.asyncio
class TestGetMine:
    async def test_returns_none_when_no_row(self) -> None:
        principal = _principal()

        repo = MagicMock()
        repo.get_for_user_and_project = AsyncMock(return_value=None)

        with patch(
            "rapidly.projects.user_property.actions.ProjectUserPropertyRepository.from_session",
            return_value=repo,
        ):
            result = await up_actions.get_mine_for_project(
                MagicMock(), principal, uuid4()
            )

        assert result is None
