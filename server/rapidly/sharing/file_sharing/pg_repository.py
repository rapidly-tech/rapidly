"""PostgreSQL repositories for file sharing audit trail.

Coexists with repository.py (Redis). PG is the durable audit store;
Redis remains the real-time operational store.
"""

from datetime import datetime, timedelta
from enum import StrEnum
from uuid import UUID

from sqlalchemy import Select, and_, func, or_, select, update

from rapidly.core.queries.base import (
    Repository,
    SoftDeleteByIdMixin,
    SoftDeleteMixin,
    SortableMixin,
    SortingClause,
)
from rapidly.identity.auth.models import (
    AuthPrincipal,
    is_user_principal,
    is_workspace_principal,
)
from rapidly.models import User
from rapidly.models.file_share_download import FileShareDownload
from rapidly.models.file_share_payment import FileSharePayment
from rapidly.models.file_share_report import FileShareReport
from rapidly.models.file_share_session import FileShareSession
from rapidly.models.workspace import Workspace
from rapidly.models.workspace_membership import WorkspaceMembership


class FileShareSessionSortProperty(StrEnum):
    created_at = "created_at"
    status = "status"
    download_count = "download_count"


class FileShareSessionRepository(
    SortableMixin[FileShareSession, FileShareSessionSortProperty],
    SoftDeleteByIdMixin[FileShareSession, UUID],
    SoftDeleteMixin[FileShareSession],
    Repository[FileShareSession],
):
    """File-share session persistence with slug lookups and download-count tracking."""

    model = FileShareSession
    sorting_enum = FileShareSessionSortProperty

    # ── Access control ──

    def get_readable_statement(
        self, auth_subject: AuthPrincipal[User | Workspace]
    ) -> Select[tuple[FileShareSession]]:
        statement = self.get_base_statement()
        if is_user_principal(auth_subject):
            user = auth_subject.subject
            statement = statement.where(
                FileShareSession.workspace_id.in_(
                    select(WorkspaceMembership.workspace_id).where(
                        WorkspaceMembership.user_id == user.id,
                        WorkspaceMembership.deleted_at.is_(None),
                    )
                )
                | (FileShareSession.user_id == user.id)
            )
        elif is_workspace_principal(auth_subject):
            statement = statement.where(
                FileShareSession.workspace_id == auth_subject.subject.id
            )
        return statement

    # ── Public stats ──

    async def get_total_count(self) -> int:
        """Return the total number of file share sessions (all statuses)."""
        stmt = (
            select(func.count())
            .select_from(FileShareSession)
            .where(
                FileShareSession.deleted_at.is_(None),
            )
        )
        result = await self.session.execute(stmt)
        return result.scalar_one()

    async def get_count_by_workspace(self, workspace_id: "UUID") -> int:
        """Return file share session count for a specific workspace."""
        stmt = (
            select(func.count())
            .select_from(FileShareSession)
            .where(
                FileShareSession.deleted_at.is_(None),
                FileShareSession.workspace_id == workspace_id,
            )
        )
        result = await self.session.execute(stmt)
        return result.scalar_one()

    # ── Slug lookups ──

    async def get_by_short_slug(self, slug: str) -> FileShareSession | None:
        statement = self.get_base_statement().where(FileShareSession.short_slug == slug)
        return await self.get_one_or_none(statement)

    async def get_by_long_slug(self, slug: str) -> FileShareSession | None:
        statement = self.get_base_statement().where(FileShareSession.long_slug == slug)
        return await self.get_one_or_none(statement)

    async def get_by_slug(self, slug: str) -> FileShareSession | None:
        """Look up a session by short slug or long slug in a single query."""
        from sqlalchemy import or_

        statement = self.get_base_statement().where(
            or_(
                FileShareSession.short_slug == slug,
                FileShareSession.long_slug == slug,
            )
        )
        return await self.get_one_or_none(statement)

    # ── Atomic updates ──

    async def increment_download_count(self, session_id: UUID) -> None:
        """Atomically increment the download count to avoid lost updates."""
        await self.session.execute(
            update(FileShareSession)
            .where(FileShareSession.id == session_id)
            .values(download_count=FileShareSession.download_count + 1)
        )
        await self.session.flush()

    # ── Filtering ──

    def apply_list_filters(
        self,
        stmt: Select[tuple[FileShareSession]],
        *,
        status: str | None = None,
        query: str | None = None,
        workspace_id: "UUID | None" = None,
    ) -> Select[tuple[FileShareSession]]:
        """Apply optional filters for session listing."""
        from rapidly.models.file_share_session import FileShareSessionStatus

        if status:
            try:
                status_enum = FileShareSessionStatus(status)
                stmt = stmt.where(FileShareSession.status == status_enum)
            except ValueError:
                pass

        if query:
            from sqlalchemy import or_

            from rapidly.core.queries.utils import escape_like

            escaped = escape_like(query)
            stmt = stmt.where(
                or_(
                    FileShareSession.short_slug.ilike(f"%{escaped}%"),
                    FileShareSession.long_slug.ilike(f"%{escaped}%"),
                    FileShareSession.file_name.ilike(f"%{escaped}%"),
                    FileShareSession.title.ilike(f"%{escaped}%"),
                )
            )

        if workspace_id is not None:
            stmt = stmt.where(FileShareSession.workspace_id == workspace_id)

        return stmt

    # ── Expiry ──

    async def expire_active_sessions(self, now: datetime) -> list[UUID]:
        """Atomically find and mark expired sessions. Returns expired IDs.

        Handles two cases:
        1. Sessions with expires_at set that have passed their expiry time
        2. Legacy sessions with no expires_at stuck in 'created' for over 24h

        Uses a single atomic UPDATE to avoid TOCTOU races where a concurrent
        download could transition a session to 'completed' between SELECT and UPDATE.
        """
        from rapidly.models.file_share_session import FileShareSessionStatus

        non_terminal = [FileShareSessionStatus.created, FileShareSessionStatus.active]
        stale_cutoff = now - timedelta(hours=24)

        update_stmt = (
            update(FileShareSession)
            .where(
                FileShareSession.deleted_at.is_(None),
                FileShareSession.status.in_(non_terminal),
                or_(
                    and_(
                        FileShareSession.expires_at.isnot(None),
                        FileShareSession.expires_at < now,
                    ),
                    and_(
                        FileShareSession.expires_at.is_(None),
                        FileShareSession.status == FileShareSessionStatus.created,
                        FileShareSession.created_at < stale_cutoff,
                    ),
                ),
            )
            .values(
                status=FileShareSessionStatus.expired,
                completed_at=now,
            )
            .returning(FileShareSession.id)
        )
        result = await self.session.execute(update_stmt)
        expired_ids = [row[0] for row in result.all()]
        if expired_ids:
            await self.session.flush()

        return expired_ids

    # ── Sorting ──

    def get_sorting_clause(
        self, property: FileShareSessionSortProperty
    ) -> SortingClause:
        match property:
            case FileShareSessionSortProperty.created_at:
                return FileShareSession.created_at
            case FileShareSessionSortProperty.status:
                return FileShareSession.status
            case FileShareSessionSortProperty.download_count:
                return FileShareSession.download_count


class FileShareDownloadRepository(
    SoftDeleteByIdMixin[FileShareDownload, UUID],
    SoftDeleteMixin[FileShareDownload],
    Repository[FileShareDownload],
):
    """Download-event records linked to file-share sessions."""

    model = FileShareDownload

    async def get_by_session_id(self, session_id: UUID) -> list[FileShareDownload]:
        statement = self.get_base_statement().where(
            FileShareDownload.session_id == session_id
        )
        results = await self.get_all(statement)
        return list(results)


class FileSharePaymentRepository(
    SoftDeleteByIdMixin[FileSharePayment, UUID],
    SoftDeleteMixin[FileSharePayment],
    Repository[FileSharePayment],
):
    """Stripe payment records for paid file-share downloads."""

    model = FileSharePayment

    async def get_by_session_id(self, session_id: UUID) -> list[FileSharePayment]:
        statement = self.get_base_statement().where(
            FileSharePayment.session_id == session_id
        )
        results = await self.get_all(statement)
        return list(results)

    async def get_by_stripe_checkout_session_id(
        self, stripe_checkout_session_id: str
    ) -> FileSharePayment | None:
        statement = self.get_base_statement().where(
            FileSharePayment.stripe_checkout_session_id == stripe_checkout_session_id
        )
        return await self.get_one_or_none(statement)

    async def get_by_stripe_payment_intent_id(
        self, stripe_payment_intent_id: str
    ) -> FileSharePayment | None:
        statement = self.get_base_statement().where(
            FileSharePayment.stripe_payment_intent_id == stripe_payment_intent_id
        )
        return await self.get_one_or_none(statement)


class FileShareReportRepository(
    SoftDeleteByIdMixin[FileShareReport, UUID],
    SoftDeleteMixin[FileShareReport],
    Repository[FileShareReport],
):
    """Abuse-report records for flagged file-share sessions."""

    model = FileShareReport

    async def get_by_session_id(self, session_id: UUID) -> list[FileShareReport]:
        statement = self.get_base_statement().where(
            FileShareReport.session_id == session_id
        )
        results = await self.get_all(statement)
        return list(results)
