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


async def credential_budgets(
    session: AsyncSession | AsyncReadSession,
    *,
    auth_subject: AuthPrincipal[User | Workspace],
    month_start: datetime,
) -> Sequence[tuple[UUID, UUID, str, str, int | None, int]]:
    """Per-credential MTD utilisation.

    Returns one row per credential the caller can see, each:
    ``(credential_id, workspace_id, provider, name,
       monthly_budget_tokens, month_to_date_tokens)``.

    A LEFT OUTER JOIN keeps credentials with zero usage in the
    result so a dashboard can show "0% used" rather than just
    omitting them. The ``LlmUsage.occurred_at`` filter goes in
    the JOIN clause (not WHERE) — putting it in WHERE would
    drop zero-usage credentials.
    """
    # Inline imports to keep the dependency graph tight.
    from rapidly.models import IntegrationCredential

    mtd_tokens = func.coalesce(
        func.sum(LlmUsage.input_tokens + LlmUsage.output_tokens), 0
    ).label("mtd_tokens")

    stmt = (
        select(
            IntegrationCredential.id,
            IntegrationCredential.workspace_id,
            IntegrationCredential.provider,
            IntegrationCredential.name,
            IntegrationCredential.monthly_budget_tokens,
            mtd_tokens,
        )
        .outerjoin(
            LlmUsage,
            (LlmUsage.credential_id == IntegrationCredential.id)
            & (LlmUsage.occurred_at >= month_start),
        )
        .where(IntegrationCredential.deleted_at.is_(None))
        .group_by(
            IntegrationCredential.id,
            IntegrationCredential.workspace_id,
            IntegrationCredential.provider,
            IntegrationCredential.name,
            IntegrationCredential.monthly_budget_tokens,
        )
        .order_by(
            IntegrationCredential.workspace_id,
            IntegrationCredential.provider,
            IntegrationCredential.name,
        )
    )

    if is_user_principal(auth_subject):
        user = auth_subject.subject
        stmt = stmt.where(
            IntegrationCredential.workspace_id.in_(
                select(WorkspaceMembership.workspace_id).where(
                    WorkspaceMembership.user_id == user.id,
                    WorkspaceMembership.deleted_at.is_(None),
                )
            )
        )
    elif is_workspace_principal(auth_subject):
        stmt = stmt.where(IntegrationCredential.workspace_id == auth_subject.subject.id)

    rows = (await session.execute(stmt)).all()
    return [tuple(r) for r in rows]  # type: ignore[misc]
