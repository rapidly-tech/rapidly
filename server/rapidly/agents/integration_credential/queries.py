"""IntegrationCredential persistence layer.

Owns the Fernet encrypt / decrypt roundtrip so the model itself
can't accidentally serialise plaintext. Consumer-side lookups
(``resolve_for_workspace``) live here too — handlers in M4.7b
will call this to fetch the runtime credential.
"""

from __future__ import annotations

import base64
import functools
import hashlib
from datetime import datetime
from uuid import UUID

from cryptography.fernet import Fernet
from sqlalchemy import Select, func, select

from rapidly.config import settings
from rapidly.core.queries import FindByIdMixin, Repository, SoftDeleteMixin
from rapidly.identity.auth.models import (
    AuthPrincipal,
    User,
    Workspace,
    is_user_principal,
    is_workspace_principal,
)
from rapidly.models import IntegrationCredential, WorkspaceMembership
from rapidly.postgres import AsyncReadSession, AsyncSession


@functools.cache
def _fernet() -> Fernet:
    """Fernet instance keyed off the app secret.

    Same derivation as ``file_sharing/queries.py::_fernet`` so an
    operator who already trusts the file-sharing-secret-rotation
    runbook can apply the same procedure here. The 32-byte digest
    is base64-urlsafe-encoded into a Fernet key.
    """
    digest = hashlib.sha256(settings.SECRET.encode()).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def encrypt_secret(plaintext: str) -> str:
    """Fernet-encrypt a credential secret for at-rest storage."""
    return _fernet().encrypt(plaintext.encode()).decode()


def decrypt_secret(ciphertext: str) -> str:
    """Decrypt a stored credential secret. Raises ``InvalidToken``
    on tamper or key rotation — callers should treat that as a
    fatal config error, not retry-able.
    """
    return _fernet().decrypt(ciphertext.encode()).decode()


class IntegrationCredentialRepository(
    SoftDeleteMixin[IntegrationCredential],
    FindByIdMixin[IntegrationCredential, UUID],
    Repository[IntegrationCredential],
):
    model = IntegrationCredential

    def get_readable_statement(
        self, auth_subject: AuthPrincipal[User | Workspace]
    ) -> Select[tuple[IntegrationCredential]]:
        statement = self.get_base_statement()

        if is_user_principal(auth_subject):
            user = auth_subject.subject
            statement = statement.where(
                IntegrationCredential.workspace_id.in_(
                    select(WorkspaceMembership.workspace_id).where(
                        WorkspaceMembership.user_id == user.id,
                        WorkspaceMembership.deleted_at.is_(None),
                    )
                )
            )
        elif is_workspace_principal(auth_subject):
            statement = statement.where(
                IntegrationCredential.workspace_id == auth_subject.subject.id
            )

        return statement


async def resolve_for_workspace(
    session: AsyncSession | AsyncReadSession,
    *,
    workspace_id: UUID,
    provider: str,
    credential_id: UUID | None = None,
) -> tuple[str, str | None] | None:
    """Look up a credential for runtime use and return the
    decrypted secret + base_url.

    Resolution order:
        1. If ``credential_id`` is given, use that exact row
           (still scoped to ``workspace_id`` — cross-tenant
           credential references are rejected silently).
        2. Otherwise look up the workspace's default for
           ``provider``.
        3. If no default exists, return ``None`` — the caller
           should fall back to env-var (M4.7a behaviour stays
           backwards-compatible until M4.7b ships).

    Returns ``(secret_plaintext, base_url)`` on hit, ``None`` on
    miss. The plaintext stays in memory for the call; callers
    should not log or persist it.
    """
    hit = await resolve_for_workspace_with_id(
        session,
        workspace_id=workspace_id,
        provider=provider,
        credential_id=credential_id,
    )
    if hit is None:
        return None
    _credential_id, secret, base_url = hit
    return secret, base_url


async def check_and_arm_budget_alert(
    session: AsyncSession,
    *,
    credential_id: UUID,
) -> None:
    """Inspect the credential's MTD vs threshold and arm the alert
    if the threshold is crossed.

    Called by the LLM handler after each ``LlmUsage`` write so the
    check is incremental — we don't have to scan the whole table
    on a cron. Idempotent within a month: re-crossing on the same
    month doesn't move ``budget_alert_triggered_at`` (the operator
    has already been notified).

    Null safety:
        - No threshold or no budget → no-op
        - Credential soft-deleted → no-op
        - MTD below threshold → no-op
        - Already triggered this month → no-op
    """
    from rapidly.core.utils import now_utc
    from rapidly.models import LlmUsage

    cred = await session.get(IntegrationCredential, credential_id)
    if cred is None:
        return
    if cred.deleted_at is not None:
        return
    if (
        cred.monthly_budget_tokens is None
        or cred.budget_alert_threshold_percent is None
    ):
        return

    now = now_utc()
    month_start = datetime(now.year, now.month, 1, tzinfo=now.tzinfo)

    # Already alerted this month?
    if (
        cred.budget_alert_triggered_at is not None
        and cred.budget_alert_triggered_at >= month_start
    ):
        return

    # Sum MTD tokens for this credential.
    mtd_stmt = select(
        func.coalesce(func.sum(LlmUsage.input_tokens + LlmUsage.output_tokens), 0)
    ).where(
        LlmUsage.credential_id == credential_id,
        LlmUsage.occurred_at >= month_start,
    )
    mtd = int((await session.execute(mtd_stmt)).scalar() or 0)

    threshold_tokens = (
        cred.monthly_budget_tokens * cred.budget_alert_threshold_percent
    ) / 100.0
    if mtd < threshold_tokens:
        return

    cred.budget_alert_triggered_at = now
    await session.flush()


async def resolve_for_workspace_with_id(
    session: AsyncSession | AsyncReadSession,
    *,
    workspace_id: UUID,
    provider: str,
    credential_id: UUID | None = None,
) -> tuple[UUID, str, str | None] | None:
    """Same as ``resolve_for_workspace`` but also returns the matched
    credential's id.

    Used by the LLM usage-tracking writer (M4.7d) so each usage
    row can be attributed to the credential that paid for it.
    Env-fallback callers should use the simpler ``resolve_for_workspace``
    surface to avoid carrying around a None id.
    """
    stmt = select(IntegrationCredential).where(
        IntegrationCredential.workspace_id == workspace_id,
        IntegrationCredential.provider == provider,
        IntegrationCredential.deleted_at.is_(None),
    )
    if credential_id is not None:
        stmt = stmt.where(IntegrationCredential.id == credential_id)
    else:
        stmt = stmt.where(IntegrationCredential.is_default.is_(True))
    row = (await session.execute(stmt)).scalar_one_or_none()
    if row is None:
        return None
    return row.id, decrypt_secret(row.secret_encrypted), row.base_url
