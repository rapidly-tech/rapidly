"""File persistence layer with polymorphic service-type queries.

``FileRepository`` provides workspace-scoped listing, ID look-up,
and bulk retrieval for all file service types (downloadable, share
media, workspace avatar).
"""

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import Select, delete, select

from rapidly.core.ordering import Sorting
from rapidly.core.queries import (
    Repository,
    SoftDeleteByIdMixin,
    SoftDeleteMixin,
    SortableMixin,
    SortingClause,
)
from rapidly.identity.auth.models import (
    AuthPrincipal,
    User,
    Workspace,
    is_user_principal,
    is_workspace_principal,
)
from rapidly.models import File, ShareMedia, WorkspaceMembership
from rapidly.models.file import FileServiceTypes, ShareMediaFile

from .ordering import FileSortProperty


class FileRepository(
    SortableMixin[File, FileSortProperty],
    SoftDeleteByIdMixin[File, UUID],
    SoftDeleteMixin[File],
    Repository[File],
):
    """Uploaded-file metadata queries with workspace scoping and S3 key lookups."""

    model = File

    # ── Reads ──

    def get_readable_statement(
        self, auth_subject: AuthPrincipal[User | Workspace]
    ) -> Select[tuple[File]]:
        statement = self.get_base_statement()

        if is_user_principal(auth_subject):
            user = auth_subject.subject
            statement = statement.where(
                File.workspace_id.in_(
                    select(WorkspaceMembership.workspace_id).where(
                        WorkspaceMembership.user_id == user.id,
                        WorkspaceMembership.deleted_at.is_(None),
                    )
                )
            )
        elif is_workspace_principal(auth_subject):
            statement = statement.where(
                File.workspace_id == auth_subject.subject.id,
            )

        return statement

    def apply_list_filters(
        self,
        stmt: Select[tuple[File]],
        *,
        workspace_id: Sequence[UUID] | None = None,
        ids: Sequence[UUID] | None = None,
    ) -> Select[tuple[File]]:
        stmt = stmt.where(File.is_uploaded.is_(True))
        if workspace_id is not None:
            stmt = stmt.where(File.workspace_id.in_(workspace_id))
        if ids is not None:
            stmt = stmt.where(File.id.in_(ids))
        return stmt

    # ── Workspace scoping ──

    async def get_all_by_workspace(
        self,
        workspace_id: UUID,
        *,
        service: FileServiceTypes | None = None,
        sorting: list[Sorting[FileSortProperty]] = [
            (FileSortProperty.created_at, True)
        ],
    ) -> Sequence[File]:
        """Get all files for an workspace, optionally filtered by service type."""
        statement = self.get_base_statement().where(
            File.workspace_id == workspace_id,
            File.is_uploaded.is_(True),
        )

        if service is not None:
            statement = statement.where(File.service == service)

        statement = self.apply_sorting(statement, sorting)

        return await self.get_all(statement)

    async def paginate_by_workspace(
        self,
        workspace_id: UUID,
        *,
        service: FileServiceTypes | None = None,
        sorting: list[Sorting[FileSortProperty]] = [
            (FileSortProperty.created_at, True)
        ],
        limit: int,
        page: int,
    ) -> tuple[list[File], int]:
        """Get paginated files for an workspace, optionally filtered by service type."""
        statement = self.get_base_statement().where(
            File.workspace_id == workspace_id,
            File.is_uploaded.is_(True),
        )

        if service is not None:
            statement = statement.where(File.service == service)

        statement = self.apply_sorting(statement, sorting)

        return await self.paginate(statement, limit=limit, page=page)

    # ── Share media queries ──

    async def delete_share_media_by_file_id(self, file_id: UUID) -> None:
        """Delete all ShareMedia rows referencing the given file."""
        await self.session.execute(
            delete(ShareMedia).where(ShareMedia.file_id == file_id)
        )

    async def get_selectable_share_media_file(
        self,
        file_id: UUID,
        *,
        workspace_id: UUID,
    ) -> ShareMediaFile | None:
        """Fetch a ShareMediaFile that is uploaded, enabled, and not deleted."""
        statement = select(ShareMediaFile).where(
            File.id == file_id,
            File.workspace_id == workspace_id,
            File.is_uploaded.is_(True),
            File.is_enabled.is_(True),
            File.deleted_at.is_(None),
        )
        result = await self.session.execute(statement)
        return result.scalar_one_or_none()

    async def get_pending_scan(self) -> Sequence[File]:
        """Return all uploaded files that still need a ClamAV scan."""
        from rapidly.models.file import FileScanStatus

        statement = self.get_base_statement().where(
            File.is_uploaded.is_(True),
            File.scan_status.is_(None) | (File.scan_status == FileScanStatus.pending),
        )
        return await self.get_all(statement)

    def get_sorting_clause(self, property: FileSortProperty) -> SortingClause:
        match property:
            case FileSortProperty.created_at:
                return File.created_at
            case FileSortProperty.file_name:
                return File.name
