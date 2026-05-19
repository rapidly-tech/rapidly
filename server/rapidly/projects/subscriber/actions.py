"""Work-item subscriber lifecycle: list, subscribe self, unsubscribe self.

Self-only mutations: a user can only subscribe or unsubscribe
themselves.  An admin-driven subscription-of-another-user endpoint
isn't included — Plane allows it, but it's easy to add later if
needed and avoids "phantom subscriptions" the receiver didn't ask
for.

Read access follows the work-item readability rule: a caller can
list subscribers of any work item they can read.
"""

from collections.abc import Sequence
from uuid import UUID

from rapidly.core.ordering import Sorting
from rapidly.core.pagination import PaginationParams, paginate
from rapidly.errors import ResourceAlreadyExists, ResourceNotFound
from rapidly.identity.auth.models import AuthPrincipal, User, Workspace
from rapidly.models import WorkItem, WorkItemSubscriber
from rapidly.postgres import AsyncReadSession, AsyncSession
from rapidly.projects.subscriber.ordering import WorkItemSubscriberSortProperty
from rapidly.projects.subscriber.queries import WorkItemSubscriberRepository
from rapidly.projects.work_item.queries import WorkItemRepository

# ── Reads ──


async def get(
    session: AsyncSession | AsyncReadSession,
    auth_subject: AuthPrincipal[User | Workspace],
    id: UUID,
) -> WorkItemSubscriber | None:
    repo = WorkItemSubscriberRepository.from_session(session)
    stmt = repo.get_readable_statement(auth_subject).where(WorkItemSubscriber.id == id)
    return await repo.get_one_or_none(stmt)


async def list_for_work_item(
    session: AsyncReadSession,
    auth_subject: AuthPrincipal[User | Workspace],
    *,
    work_item_id: UUID,
    pagination: PaginationParams,
    sorting: Sequence[Sorting[WorkItemSubscriberSortProperty]],
) -> tuple[Sequence[WorkItemSubscriber], int]:
    await _readable_work_item(session, auth_subject, work_item_id)

    repo = WorkItemSubscriberRepository.from_session(session)
    statement = repo.get_readable_statement(auth_subject).where(
        WorkItemSubscriber.work_item_id == work_item_id
    )
    statement = repo.apply_sorting(statement, sorting)
    return await paginate(session, statement, pagination=pagination)


async def list_subscribed_for_user(
    session: AsyncReadSession,
    auth_subject: AuthPrincipal[User],
    *,
    pagination: PaginationParams,
    sorting: Sequence[Sorting[WorkItemSubscriberSortProperty]],
) -> tuple[Sequence[WorkItemSubscriber], int]:
    """Return the caller's own subscriptions."""
    repo = WorkItemSubscriberRepository.from_session(session)
    statement = repo.get_readable_statement(auth_subject).where(
        WorkItemSubscriber.user_id == auth_subject.subject.id
    )
    statement = repo.apply_sorting(statement, sorting)
    return await paginate(session, statement, pagination=pagination)


# ── Writes ──


async def subscribe(
    session: AsyncSession,
    auth_subject: AuthPrincipal[User],
    *,
    work_item_id: UUID,
) -> WorkItemSubscriber:
    """Subscribe the calling user to a work item.

    Why this is self-only:
    - Allowing one user to subscribe another would let any project
      member spam notifications to a teammate. Keeping it self-only
      preserves the principle of "you control your own notifications."
    """
    await _readable_work_item(session, auth_subject, work_item_id)

    repo = WorkItemSubscriberRepository.from_session(session)
    user_id = auth_subject.subject.id
    existing = await repo.get_for_user_and_work_item(user_id, work_item_id)
    if existing is not None:
        raise ResourceAlreadyExists("You are already subscribed to this work item.")

    subscription = WorkItemSubscriber(work_item_id=work_item_id, user_id=user_id)
    return await repo.create(subscription, flush=True)


async def unsubscribe(
    session: AsyncSession,
    auth_subject: AuthPrincipal[User],
    subscription: WorkItemSubscriber,
) -> None:
    """Remove a subscription. Caller must be the subscriber.

    The route resolves the subscription through the readable statement
    (workspace-bounded), then this layer enforces that the caller is the
    *subject* of the subscription — otherwise any project member could
    silently mute a teammate's notifications.
    """
    if subscription.user_id != auth_subject.subject.id:
        raise ResourceNotFound()

    repo = WorkItemSubscriberRepository.from_session(session)
    await repo.soft_delete(subscription)


# ── Helpers ──


async def _readable_work_item(
    session: AsyncSession | AsyncReadSession,
    auth_subject: AuthPrincipal[User | Workspace],
    work_item_id: UUID,
) -> WorkItem:
    repo = WorkItemRepository.from_session(session)
    work_item = await repo.get_one_or_none(
        repo.get_readable_statement(auth_subject).where(WorkItem.id == work_item_id)
    )
    if work_item is None:
        raise ResourceNotFound("Work item not found.")
    return work_item
