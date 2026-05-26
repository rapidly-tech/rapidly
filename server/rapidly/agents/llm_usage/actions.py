"""LlmUsage read + rollup actions."""

from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from uuid import UUID

from rapidly.agents.llm_usage.queries import LlmUsageRepository, rollup_grouped
from rapidly.agents.llm_usage.types import UsageRollupResponse, UsageRollupRow
from rapidly.core.pagination import PaginationParams, paginate
from rapidly.identity.auth.models import AuthPrincipal, User, Workspace
from rapidly.models import LlmUsage
from rapidly.postgres import AsyncReadSession

# Default rollup window. 24h matches the most common operator
# question ("are we burning more tokens than yesterday?") and
# bounds the row count for a busy workspace.
_DEFAULT_WINDOW = timedelta(hours=24)
# Cap on requested window. 90 days keeps the per-query row count
# bounded; longer rollups should go through an offline export.
_MAX_WINDOW = timedelta(days=90)


async def list_usage(
    session: AsyncReadSession,
    auth_subject: AuthPrincipal[User | Workspace],
    *,
    credential_id: UUID | None = None,
    provider: str | None = None,
    pagination: PaginationParams,
) -> tuple[Sequence[LlmUsage], int]:
    repo = LlmUsageRepository.from_session(session)
    statement = repo.get_readable_statement(auth_subject)
    if credential_id is not None:
        statement = statement.where(LlmUsage.credential_id == credential_id)
    if provider is not None:
        statement = statement.where(LlmUsage.provider == provider)
    statement = statement.order_by(LlmUsage.occurred_at.desc())
    return await paginate(session, statement, pagination=pagination)


async def rollup(
    session: AsyncReadSession,
    auth_subject: AuthPrincipal[User | Workspace],
    *,
    window_start: datetime | None = None,
    window_end: datetime | None = None,
    credential_id: UUID | None = None,
    provider: str | None = None,
) -> UsageRollupResponse:
    """Return a grouped rollup over the given window.

    Default window is the last 24 hours. Operators asking
    "how much did we spend last week" pass an explicit
    ``window_start`` — capped at 90 days for sanity.
    """
    end = window_end or datetime.now(UTC)
    start = window_start or (end - _DEFAULT_WINDOW)
    # Clamp absurd windows. The endpoint accepts long windows but
    # the SQL aggregate doesn't get more useful past a few months
    # and the row count balloons.
    if end - start > _MAX_WINDOW:
        start = end - _MAX_WINDOW

    rows = await rollup_grouped(
        session,
        auth_subject=auth_subject,
        window_start=start,
        window_end=end,
        credential_id=credential_id,
        provider=provider,
    )

    rollup_rows: list[UsageRollupRow] = []
    for ws_id, cred_id, prov, model, input_t, output_t, calls in rows:
        rollup_rows.append(
            UsageRollupRow(
                workspace_id=ws_id,
                credential_id=cred_id,
                provider=prov,
                model=model,
                input_tokens=int(input_t),
                output_tokens=int(output_t),
                total_tokens=int(input_t) + int(output_t),
                call_count=int(calls),
            )
        )
    return UsageRollupResponse(
        window_start=start,
        window_end=end,
        rows=rollup_rows,
    )
