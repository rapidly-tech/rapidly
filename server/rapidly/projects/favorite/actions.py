"""User favorite lifecycle: list, get, create, delete.

The non-obvious bit is ``_assert_entity_readable`` — before persisting a
favorite, we resolve the polymorphic ``(entity_type, entity_id)`` pair
against the matching domain repository and reject with 404 if it isn't
readable.  Without this check a user could star a UUID they have no
business knowing about.
"""

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy.exc import IntegrityError

from rapidly.core.ordering import Sorting
from rapidly.core.pagination import PaginationParams, paginate
from rapidly.errors import ResourceAlreadyExists, ResourceNotFound
from rapidly.identity.auth.models import AuthPrincipal, User
from rapidly.models import UserFavorite, UserFavoriteEntityType
from rapidly.postgres import AsyncReadSession, AsyncSession
from rapidly.projects.cycle.queries import ProjectCycleRepository
from rapidly.projects.favorite.ordering import UserFavoriteSortProperty
from rapidly.projects.favorite.queries import UserFavoriteRepository
from rapidly.projects.favorite.types import UserFavoriteCreate
from rapidly.projects.module.queries import ProjectModuleRepository
from rapidly.projects.page.queries import ProjectPageRepository
from rapidly.projects.project.queries import ProjectRepository
from rapidly.projects.work_item.queries import WorkItemRepository


async def get(
    session: AsyncSession | AsyncReadSession,
    auth_subject: AuthPrincipal[User],
    id: UUID,
) -> UserFavorite | None:
    repo = UserFavoriteRepository.from_session(session)
    stmt = repo.get_readable_statement(auth_subject).where(UserFavorite.id == id)
    return await repo.get_one_or_none(stmt)


async def list(
    session: AsyncReadSession,
    auth_subject: AuthPrincipal[User],
    *,
    entity_type: UserFavoriteEntityType | None = None,
    pagination: PaginationParams,
    sorting: Sequence[Sorting[UserFavoriteSortProperty]],
) -> tuple[Sequence[UserFavorite], int]:
    repo = UserFavoriteRepository.from_session(session)
    statement = repo.get_readable_statement(auth_subject)
    if entity_type is not None:
        statement = statement.where(UserFavorite.entity_type == entity_type)
    statement = repo.apply_sorting(statement, sorting)
    return await paginate(session, statement, pagination=pagination)


async def create(
    session: AsyncSession,
    auth_subject: AuthPrincipal[User],
    data: UserFavoriteCreate,
) -> UserFavorite:
    await _assert_entity_readable(session, auth_subject, data.entity_type, data.entity_id)

    repo = UserFavoriteRepository.from_session(session)
    favorite = UserFavorite(
        user_id=auth_subject.subject.id,
        entity_type=data.entity_type,
        entity_id=data.entity_id,
    )
    try:
        return await repo.create(favorite, flush=True)
    except IntegrityError as exc:
        # UNIQUE (user_id, entity_type, entity_id) collision — the user
        # already favorited this entity.  Surface as 409 so clients can
        # treat the operation as idempotent if they choose to.
        raise ResourceAlreadyExists(
            "This entity is already in your favorites.",
        ) from exc


async def delete(
    session: AsyncSession,
    auth_subject: AuthPrincipal[User],
    favorite: UserFavorite,
) -> None:
    # `favorite` came from `get(...)` which already applied the
    # user-scoped readable statement, so the caller has been verified.
    repo = UserFavoriteRepository.from_session(session)
    await repo.soft_delete(favorite)


async def _assert_entity_readable(
    session: AsyncSession,
    auth_subject: AuthPrincipal[User],
    entity_type: UserFavoriteEntityType,
    entity_id: UUID,
) -> None:
    """Reject 404 if ``entity_id`` is not reachable by ``auth_subject``."""

    if entity_type is UserFavoriteEntityType.project:
        repo = ProjectRepository.from_session(session)
        stmt = repo.get_readable_statement(auth_subject).where(
            repo.model.id == entity_id
        )
        if await repo.get_one_or_none(stmt) is None:
            raise ResourceNotFound("Project not found.")
        return

    if entity_type is UserFavoriteEntityType.cycle:
        cycle_repo = ProjectCycleRepository.from_session(session)
        cycle_stmt = cycle_repo.get_readable_statement(auth_subject).where(
            cycle_repo.model.id == entity_id
        )
        if await cycle_repo.get_one_or_none(cycle_stmt) is None:
            raise ResourceNotFound("Cycle not found.")
        return

    if entity_type is UserFavoriteEntityType.module:
        module_repo = ProjectModuleRepository.from_session(session)
        module_stmt = module_repo.get_readable_statement(auth_subject).where(
            module_repo.model.id == entity_id
        )
        if await module_repo.get_one_or_none(module_stmt) is None:
            raise ResourceNotFound("Module not found.")
        return

    if entity_type is UserFavoriteEntityType.page:
        page_repo = ProjectPageRepository.from_session(session)
        page_stmt = page_repo.get_readable_statement(auth_subject).where(
            page_repo.model.id == entity_id
        )
        if await page_repo.get_one_or_none(page_stmt) is None:
            raise ResourceNotFound("Page not found.")
        return

    if entity_type is UserFavoriteEntityType.work_item:
        work_item_repo = WorkItemRepository.from_session(session)
        work_item_stmt = work_item_repo.get_readable_statement(auth_subject).where(
            work_item_repo.model.id == entity_id
        )
        if await work_item_repo.get_one_or_none(work_item_stmt) is None:
            raise ResourceNotFound("Work item not found.")
        return
