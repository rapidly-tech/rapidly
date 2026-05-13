"""Tests for ``rapidly.projects.favorite.actions``.

The non-obvious invariant exercised here is the entity-resolution gate:
``create(...)`` must consult the matching domain Repository's readable
statement before persisting, so a user cannot favorite a UUID they
can't see.  We dispatch over all 5 ``UserFavoriteEntityType`` values to
prove the dispatch table stays in sync with the enum.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from sqlalchemy.exc import IntegrityError

from rapidly.errors import ResourceAlreadyExists, ResourceNotFound
from rapidly.identity.auth.models import AuthPrincipal
from rapidly.models import User, UserFavorite, UserFavoriteEntityType
from rapidly.projects.favorite import actions as favorite_actions
from rapidly.projects.favorite.types import UserFavoriteCreate


def _user_principal() -> AuthPrincipal[User]:
    return AuthPrincipal(
        subject=User(id=uuid4(), email="dev@example.com"),
        scopes=set(),
        session=None,
    )


_TYPE_TO_REPO_PATH: dict[UserFavoriteEntityType, str] = {
    UserFavoriteEntityType.project: (
        "rapidly.projects.favorite.actions.ProjectRepository.from_session"
    ),
    UserFavoriteEntityType.cycle: (
        "rapidly.projects.favorite.actions.ProjectCycleRepository.from_session"
    ),
    UserFavoriteEntityType.module: (
        "rapidly.projects.favorite.actions.ProjectModuleRepository.from_session"
    ),
    UserFavoriteEntityType.page: (
        "rapidly.projects.favorite.actions.ProjectPageRepository.from_session"
    ),
    UserFavoriteEntityType.work_item: (
        "rapidly.projects.favorite.actions.WorkItemRepository.from_session"
    ),
}


@pytest.mark.asyncio
class TestCreate:
    @pytest.mark.parametrize("entity_type", list(UserFavoriteEntityType))
    async def test_persists_when_entity_is_readable(
        self, entity_type: UserFavoriteEntityType
    ) -> None:
        principal = _user_principal()
        session = MagicMock()
        entity_id = uuid4()

        target_repo = MagicMock()
        target_repo.get_readable_statement = MagicMock(return_value=MagicMock())
        target_repo.get_one_or_none = AsyncMock(return_value=MagicMock(id=entity_id))
        target_repo.model = MagicMock()

        favorite_repo = MagicMock()
        favorite_repo.create = AsyncMock(
            return_value=UserFavorite(
                id=uuid4(),
                user_id=principal.subject.id,
                entity_type=entity_type,
                entity_id=entity_id,
            )
        )

        with (
            patch(_TYPE_TO_REPO_PATH[entity_type], return_value=target_repo),
            patch(
                "rapidly.projects.favorite.actions.UserFavoriteRepository.from_session",
                return_value=favorite_repo,
            ),
        ):
            result = await favorite_actions.create(
                session,
                principal,
                UserFavoriteCreate(entity_type=entity_type, entity_id=entity_id),
            )

        assert result.entity_id == entity_id
        assert result.entity_type == entity_type
        favorite_repo.create.assert_awaited_once()

    @pytest.mark.parametrize("entity_type", list(UserFavoriteEntityType))
    async def test_rejects_unreadable_entity(
        self, entity_type: UserFavoriteEntityType
    ) -> None:
        # Pin: each Repository's readable statement is the boundary.
        # If get_one_or_none returns None, the action MUST raise 404
        # without ever touching UserFavoriteRepository.
        principal = _user_principal()
        session = MagicMock()

        target_repo = MagicMock()
        target_repo.get_readable_statement = MagicMock(return_value=MagicMock())
        target_repo.get_one_or_none = AsyncMock(return_value=None)
        target_repo.model = MagicMock()

        favorite_repo = MagicMock()
        favorite_repo.create = AsyncMock()

        with (
            patch(_TYPE_TO_REPO_PATH[entity_type], return_value=target_repo),
            patch(
                "rapidly.projects.favorite.actions.UserFavoriteRepository.from_session",
                return_value=favorite_repo,
            ),
        ):
            with pytest.raises(ResourceNotFound):
                await favorite_actions.create(
                    session,
                    principal,
                    UserFavoriteCreate(entity_type=entity_type, entity_id=uuid4()),
                )

        favorite_repo.create.assert_not_awaited()

    async def test_duplicate_raises_already_exists(self) -> None:
        # Pin: UNIQUE (user, entity_type, entity_id) collision must
        # surface as 409, not the raw IntegrityError.  Clients rely on
        # the 409 to treat the operation as idempotent.
        principal = _user_principal()
        session = MagicMock()
        entity_id = uuid4()

        target_repo = MagicMock()
        target_repo.get_readable_statement = MagicMock(return_value=MagicMock())
        target_repo.get_one_or_none = AsyncMock(return_value=MagicMock(id=entity_id))
        target_repo.model = MagicMock()

        favorite_repo = MagicMock()
        favorite_repo.create = AsyncMock(
            side_effect=IntegrityError("INSERT", {}, Exception("dup"))
        )

        with (
            patch(
                _TYPE_TO_REPO_PATH[UserFavoriteEntityType.project],
                return_value=target_repo,
            ),
            patch(
                "rapidly.projects.favorite.actions.UserFavoriteRepository.from_session",
                return_value=favorite_repo,
            ),
        ):
            with pytest.raises(ResourceAlreadyExists):
                await favorite_actions.create(
                    session,
                    principal,
                    UserFavoriteCreate(
                        entity_type=UserFavoriteEntityType.project,
                        entity_id=entity_id,
                    ),
                )


@pytest.mark.asyncio
class TestList:
    async def test_filter_by_entity_type_narrows_statement(self) -> None:
        # Pin: filter clause must be applied to the readable statement,
        # not after the fact in Python.  Asserting via the where(...)
        # chain that the entity_type clause is attached.
        principal = _user_principal()
        session = MagicMock()

        statement = MagicMock()
        filtered = MagicMock()
        statement.where.return_value = filtered
        filtered.where.return_value = filtered

        repo = MagicMock()
        repo.get_readable_statement = MagicMock(return_value=statement)
        repo.apply_sorting = MagicMock(return_value=filtered)

        with (
            patch(
                "rapidly.projects.favorite.actions.UserFavoriteRepository.from_session",
                return_value=repo,
            ),
            patch(
                "rapidly.projects.favorite.actions.paginate",
                new_callable=AsyncMock,
                return_value=([], 0),
            ),
        ):
            await favorite_actions.list(
                session,
                principal,
                entity_type=UserFavoriteEntityType.page,
                pagination=MagicMock(),
                sorting=[],
            )

        statement.where.assert_called_once()


@pytest.mark.asyncio
class TestDelete:
    async def test_soft_deletes_via_repo(self) -> None:
        principal = _user_principal()
        session = MagicMock()
        favorite = UserFavorite(
            id=uuid4(),
            user_id=principal.subject.id,
            entity_type=UserFavoriteEntityType.project,
            entity_id=uuid4(),
        )

        repo = MagicMock()
        repo.soft_delete = AsyncMock()

        with patch(
            "rapidly.projects.favorite.actions.UserFavoriteRepository.from_session",
            return_value=repo,
        ):
            await favorite_actions.delete(session, principal, favorite)

        repo.soft_delete.assert_awaited_once_with(favorite)
