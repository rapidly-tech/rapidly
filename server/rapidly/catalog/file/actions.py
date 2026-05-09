"""File upload lifecycle: presigned URLs, multipart completion, and malware scanning."""

import uuid
from collections.abc import Sequence
from datetime import datetime

import structlog

from rapidly.core.pagination import PaginationParams
from rapidly.identity.auth.models import AuthPrincipal
from rapidly.models import User, Workspace
from rapidly.models.file import File, FileScanStatus, ShareMediaFile
from rapidly.postgres import AsyncReadSession, AsyncSession
from rapidly.worker import dispatch_task

from .queries import FileRepository
from .s3 import S3_SERVICES
from .types import (
    FileCreate,
    FilePatch,
    FileUpload,
    FileUploadCompleted,
)

_log = structlog.get_logger(__name__)


# ── Queries ───────────────────────────────────────────────────────


async def list(
    session: AsyncReadSession,
    auth_subject: AuthPrincipal[User | Workspace],
    *,
    workspace_id: Sequence[uuid.UUID] | None = None,
    ids: Sequence[uuid.UUID] | None = None,
    pagination: PaginationParams,
) -> tuple[Sequence[File], int]:
    repo = FileRepository.from_session(session)
    stmt = repo.get_readable_statement(auth_subject)
    stmt = repo.apply_list_filters(stmt, workspace_id=workspace_id, ids=ids)
    return await repo.paginate(stmt, limit=pagination.limit, page=pagination.page)


async def get(
    session: AsyncSession,
    auth_subject: AuthPrincipal[User | Workspace],
    id: uuid.UUID,
) -> File | None:
    repo = FileRepository.from_session(session)
    stmt = repo.get_readable_statement(auth_subject).where(File.id == id)
    return await repo.get_one_or_none(stmt)


# ── Mutations ──────────────────────────────────────────────────────


async def patch(
    session: AsyncSession,
    *,
    file: File,
    patches: FilePatch,
) -> File:
    dirty = False
    if patches.name:
        file.name = patches.name
        dirty = True
    if patches.version:
        file.version = patches.version
        dirty = True

    if not dirty:
        return file

    await session.flush()
    return file


async def generate_presigned_upload(
    session: AsyncSession,
    *,
    workspace: Workspace,
    create_schema: FileCreate,
) -> FileUpload:
    s3_service = S3_SERVICES[create_schema.service]
    upload = s3_service.create_multipart_upload(
        create_schema, namespace=create_schema.service.value
    )

    instance = File(
        workspace=workspace,
        service=create_schema.service,
        is_enabled=True,
        is_uploaded=False,
        **upload.model_dump(exclude={"upload", "workspace_id", "size_readable"}),
    )
    repo = FileRepository.from_session(session)
    await repo.create(instance, flush=True)
    if instance.id is None:
        raise ValueError("File instance ID must not be None after flush")

    return FileUpload(
        is_uploaded=instance.is_uploaded,
        version=instance.version,
        service=create_schema.service,
        **upload.model_dump(),
    )


async def complete_upload(
    session: AsyncSession,
    *,
    file: File,
    completed_schema: FileUploadCompleted,
) -> File:
    s3 = S3_SERVICES[file.service]
    result = s3.complete_multipart_upload(completed_schema)

    file.is_uploaded = True
    if result.checksum_etag:
        file.checksum_etag = result.checksum_etag
    if result.last_modified_at:
        file.last_modified_at = result.last_modified_at
    if result.storage_version:
        file.storage_version = result.storage_version

    file.scan_status = FileScanStatus.pending
    await session.flush()
    if file.checksum_etag is None:
        raise ValueError("file.checksum_etag must not be None after upload completion")
    if file.last_modified_at is None:
        raise ValueError(
            "file.last_modified_at must not be None after upload completion"
        )

    dispatch_task("file.scan", file_id=file.id)
    _log.info("file.scan.queued", file_id=str(file.id))
    return file


# ── Downloads ──────────────────────────────────────────────────────


def generate_download_url(file: File) -> tuple[str, datetime]:
    """Return a presigned download URL and its expiry timestamp."""
    s3 = S3_SERVICES[file.service]
    return s3.generate_presigned_download_url(
        path=file.path, filename=file.name, mime_type=file.mime_type
    )


# ── Deletion ──────────────────────────────────────────────────────


async def delete(session: AsyncSession, *, file: File) -> bool:
    file.set_deleted_at()
    if file.deleted_at is None:
        raise ValueError("file.deleted_at must be set after set_deleted_at()")

    repo = FileRepository.from_session(session)
    await repo.delete_share_media_by_file_id(file.id)

    s3 = S3_SERVICES[file.service]
    removed = s3.delete_file(file.path)
    _log.info("file.deleted", file_id=file.id, s3_removed=removed)
    return True


async def get_selectable_share_media_file(
    session: AsyncSession,
    id: uuid.UUID,
    *,
    workspace_id: uuid.UUID,
) -> ShareMediaFile | None:
    repo = FileRepository.from_session(session)
    return await repo.get_selectable_share_media_file(id, workspace_id=workspace_id)
