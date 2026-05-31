"""Activity read + emit.

Read paths honour the standard workspace-isolation gate.  ``emit`` is
called by sibling modules (work_item, comment) inside the *same* unit
of work — it adds the row and flushes so subsequent reads in the same
transaction see it.  Emit failures are surfaced (not swallowed) because
a silent activity-log drop produces an unauditable trail and is harder
to detect than a 500.
"""

from collections.abc import Sequence
from typing import Any
from uuid import UUID

from rapidly.core.ordering import Sorting
from rapidly.core.pagination import PaginationParams, paginate
from rapidly.identity.auth.models import (
    AuthPrincipal,
    User,
    Workspace,
    is_user_principal,
)
from rapidly.models import WorkItem, WorkItemActivity, WorkItemActivityVerb
from rapidly.postgres import AsyncReadSession, AsyncSession
from rapidly.projects.activity.ordering import WorkItemActivitySortProperty
from rapidly.projects.activity.queries import WorkItemActivityRepository

# ── Reads ──


async def list_for_work_item(
    session: AsyncReadSession,
    auth_subject: AuthPrincipal[User | Workspace],
    *,
    work_item_id: UUID,
    pagination: PaginationParams,
    sorting: Sequence[Sorting[WorkItemActivitySortProperty]],
) -> tuple[Sequence[WorkItemActivity], int]:
    repo = WorkItemActivityRepository.from_session(session)
    statement = repo.get_readable_statement(auth_subject).where(
        WorkItemActivity.work_item_id == work_item_id
    )
    # Single sort key today; honour direction.
    for criterion, is_desc in sorting:
        column = getattr(WorkItemActivity, criterion.value)
        statement = statement.order_by(column.desc() if is_desc else column.asc())
    return await paginate(session, statement, pagination=pagination)


# ── Emit ──


async def emit(
    session: AsyncSession,
    *,
    work_item: WorkItem,
    actor: AuthPrincipal[User | Workspace] | None,
    verb: WorkItemActivityVerb,
    field: str | None = None,
    old_value: Any | None = None,
    new_value: Any | None = None,
    payload: dict[str, Any] | None = None,
    comment_id: UUID | None = None,
) -> WorkItemActivity:
    """Persist an activity row.

    Strings come pre-truncated to fit the ``VARCHAR(512)`` columns —
    callers passing rich text should stringify and slice.  Anything
    bigger than that belongs in ``payload``.
    """
    activity = WorkItemActivity(
        work_item_id=work_item.id,
        actor_id=(
            actor.subject.id if actor is not None and is_user_principal(actor) else None
        ),
        verb=verb,
        field=field,
        old_value=_stringify(old_value),
        new_value=_stringify(new_value),
        payload=payload,
        comment_id=comment_id,
    )
    session.add(activity)
    await session.flush()
    return activity


def _stringify(value: Any) -> str | None:
    if value is None:
        return None
    s = str(value)
    return s[:512]
