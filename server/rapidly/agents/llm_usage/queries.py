"""LlmUsage persistence + rollup-aggregate helpers."""

from collections.abc import Sequence
from datetime import datetime
from uuid import UUID

from sqlalchemy import Select, func, select

from rapidly.core.queries import FindByIdMixin, Repository
from rapidly.identity.auth.models import (
    AuthPrincipal,
    User,
    Workspace,
    is_user_principal,
    is_workspace_principal,
)
from rapidly.models import LlmUsage, WorkspaceMembership
from rapidly.postgres import AsyncReadSession, AsyncSession


class LlmUsageRepository(
    FindByIdMixin[LlmUsage, UUID],
    Repository[LlmUsage],
):
    model = LlmUsage

    def get_readable_statement(
        self, auth_subject: AuthPrincipal[User | Workspace]
    ) -> Select[tuple[LlmUsage]]:
        statement = self.get_base_statement()

        if is_user_principal(auth_subject):
            user = auth_subject.subject
            statement = statement.where(
                LlmUsage.workspace_id.in_(
                    select(WorkspaceMembership.workspace_id).where(
                        WorkspaceMembership.user_id == user.id,
                        WorkspaceMembership.deleted_at.is_(None),
                    )
                )
            )
        elif is_workspace_principal(auth_subject):
            statement = statement.where(
                LlmUsage.workspace_id == auth_subject.subject.id
            )

        return statement


async def rollup_grouped(
    session: AsyncSession | AsyncReadSession,
    *,
    auth_subject: AuthPrincipal[User | Workspace],
    window_start: datetime,
    window_end: datetime,
    credential_id: UUID | None = None,
    provider: str | None = None,
) -> Sequence[tuple[UUID, UUID | None, str, str, int, int, int]]:
    """Aggregate usage rows grouped by
    ``(workspace_id, credential_id, provider, model)``.

    Returns a sequence of tuples:
    ``(workspace_id, credential_id, provider, model,
       input_tokens_sum, output_tokens_sum, call_count)``.

    Tenancy is applied inline rather than reusing the
    repository's ``get_readable_statement`` because the latter
    targets a row-shaped SELECT; the rollup needs aggregate
    columns. Keeping the same tenancy clauses literally aligns
    the two paths.
    """
    stmt = (
        select(
            LlmUsage.workspace_id,
            LlmUsage.credential_id,
            LlmUsage.provider,
            LlmUsage.model,
            func.coalesce(func.sum(LlmUsage.input_tokens), 0).label("input_tokens"),
            func.coalesce(func.sum(LlmUsage.output_tokens), 0).label("output_tokens"),
            func.count(LlmUsage.id).label("call_count"),
        )
        .where(LlmUsage.occurred_at >= window_start)
        .where(LlmUsage.occurred_at < window_end)
        .group_by(
            LlmUsage.workspace_id,
            LlmUsage.credential_id,
            LlmUsage.provider,
            LlmUsage.model,
        )
        .order_by(
            LlmUsage.workspace_id,
            LlmUsage.provider,
            LlmUsage.model,
        )
    )

    # Tenancy — same shape as ``get_readable_statement`` above.
    if is_user_principal(auth_subject):
        user = auth_subject.subject
        stmt = stmt.where(
            LlmUsage.workspace_id.in_(
                select(WorkspaceMembership.workspace_id).where(
                    WorkspaceMembership.user_id == user.id,
                    WorkspaceMembership.deleted_at.is_(None),
                )
            )
        )
    elif is_workspace_principal(auth_subject):
        stmt = stmt.where(LlmUsage.workspace_id == auth_subject.subject.id)

    if credential_id is not None:
        stmt = stmt.where(LlmUsage.credential_id == credential_id)
    if provider is not None:
        stmt = stmt.where(LlmUsage.provider == provider)

    rows = (await session.execute(stmt)).all()
    return [tuple(r) for r in rows]  # type: ignore[misc]
