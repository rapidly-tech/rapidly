"""Tests for cycle + module user-property actions.

Invariants pinned (symmetric for both flows):

- ``upsert`` returns 404 when the parent resource isn't readable
  (existence-leak guard).
- A new row is created with payload data when no row exists.
- Partial update keeps unmentioned fields intact.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from rapidly.errors import ResourceNotFound
from rapidly.identity.auth.models import AuthPrincipal
from rapidly.models import (
    ProjectCycleUserProperty,
    ProjectModuleUserProperty,
    User,
)
from rapidly.projects.resource_user_property import actions as up_actions
from rapidly.projects.resource_user_property.types import (
    ProjectCycleUserPropertyUpsert,
    ProjectModuleUserPropertyUpsert,
)


def _principal() -> AuthPrincipal[User]:
    return AuthPrincipal(
        subject=User(id=uuid4(), email="dev@example.com"),
        scopes=set(),
        session=None,
    )


def _cycle_row(user_id: Any, cycle_id: Any) -> ProjectCycleUserProperty:
    return ProjectCycleUserProperty(
        id=uuid4(),
        cycle_id=cycle_id,
        user_id=user_id,
        filters={},
        display_filters={"order_by": "-created_at"},
        display_properties={},
    )


def _module_row(user_id: Any, module_id: Any) -> ProjectModuleUserProperty:
    return ProjectModuleUserProperty(
        id=uuid4(),
        module_id=module_id,
        user_id=user_id,
        filters={},
        display_filters={"order_by": "-created_at"},
        display_properties={},
    )


@pytest.mark.asyncio
class TestCyclePropsUpsert:
    async def test_unreadable_cycle_rejected(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        principal = _principal()

        async def _no_access(*_a: Any, **_k: Any) -> None:
            raise ResourceNotFound()

        monkeypatch.setattr(
            "rapidly.projects.resource_user_property.actions._ensure_cycle_readable",
            _no_access,
        )

        with pytest.raises(ResourceNotFound):
            await up_actions.upsert_cycle_props(
                MagicMock(),
                principal,
                ProjectCycleUserPropertyUpsert(cycle_id=uuid4(), filters={"x": 1}),
            )

    async def test_creates_new_row(self, monkeypatch: pytest.MonkeyPatch) -> None:
        principal = _principal()
        cycle_id = uuid4()

        async def _ok(*_a: Any, **_k: Any) -> None:
            return None

        monkeypatch.setattr(
            "rapidly.projects.resource_user_property.actions._ensure_cycle_readable",
            _ok,
        )

        captured: list[Any] = []
        repo = MagicMock()
        repo.get_for_user_and_cycle = AsyncMock(return_value=None)

        async def _create(obj: Any, flush: bool = False) -> Any:
            captured.append(obj)
            return obj

        repo.create = _create

        with patch(
            "rapidly.projects.resource_user_property.actions.ProjectCycleUserPropertyRepository.from_session",
            return_value=repo,
        ):
            await up_actions.upsert_cycle_props(
                MagicMock(),
                principal,
                ProjectCycleUserPropertyUpsert(
                    cycle_id=cycle_id, display_filters={"order_by": "priority"}
                ),
            )

        assert captured[0].cycle_id == cycle_id
        assert captured[0].user_id == principal.subject.id
        assert captured[0].display_filters == {"order_by": "priority"}
        assert captured[0].filters == {}


@pytest.mark.asyncio
class TestModulePropsUpsert:
    async def test_unreadable_module_rejected(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        principal = _principal()

        async def _no_access(*_a: Any, **_k: Any) -> None:
            raise ResourceNotFound()

        monkeypatch.setattr(
            "rapidly.projects.resource_user_property.actions._ensure_module_readable",
            _no_access,
        )

        with pytest.raises(ResourceNotFound):
            await up_actions.upsert_module_props(
                MagicMock(),
                principal,
                ProjectModuleUserPropertyUpsert(module_id=uuid4(), filters={"x": 1}),
            )

    async def test_partial_update_keeps_others(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        principal = _principal()
        existing = _module_row(principal.subject.id, uuid4())

        async def _ok(*_a: Any, **_k: Any) -> None:
            return None

        monkeypatch.setattr(
            "rapidly.projects.resource_user_property.actions._ensure_module_readable",
            _ok,
        )

        repo = MagicMock()
        repo.get_for_user_and_module = AsyncMock(return_value=existing)
        repo.update = AsyncMock(return_value=existing)

        with patch(
            "rapidly.projects.resource_user_property.actions.ProjectModuleUserPropertyRepository.from_session",
            return_value=repo,
        ):
            await up_actions.upsert_module_props(
                MagicMock(),
                principal,
                ProjectModuleUserPropertyUpsert(
                    module_id=existing.module_id,
                    filters={"priority": "high"},
                ),
            )

        assert repo.update.await_count == 1
        _, kwargs = repo.update.call_args
        assert kwargs["update_dict"] == {"filters": {"priority": "high"}}
