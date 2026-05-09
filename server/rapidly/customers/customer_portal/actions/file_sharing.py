"""Customer portal file-sharing actions.

Business logic for listing file sharing sessions, downloads, and payments
within a customer portal context (member access only).
"""

from collections.abc import Sequence

from pydantic import UUID4
from sqlalchemy import Select

from rapidly.core.db.postgres import AsyncReadSession
from rapidly.core.ordering import Sorting
from rapidly.core.pagination import PaginationParams
from rapidly.identity.auth.models import AuthPrincipal, Subject, is_member_principal
from rapidly.models.file_share_download import FileShareDownload
from rapidly.models.file_share_payment import FileSharePayment
from rapidly.models.file_share_session import FileShareSession
from rapidly.sharing.file_sharing.pg_repository import (
    FileShareDownloadRepository,
    FileSharePaymentRepository,
    FileShareSessionRepository,
    FileShareSessionSortProperty,
)


async def list_sessions(
    session: AsyncReadSession,
    auth_subject: AuthPrincipal[Subject],
    *,
    pagination: PaginationParams,
    sorting: Sequence[Sorting[FileShareSessionSortProperty]],
) -> tuple[list[FileShareSession], int]:
    """List file sharing sessions for the authenticated member's workspace.

    Returns an empty list if the auth subject is not a member.
    """
    if not is_member_principal(auth_subject):
        return [], 0

    member = auth_subject.subject
    repo = FileShareSessionRepository.from_session(session)
    statement: Select[tuple[FileShareSession]] = repo.get_base_statement().where(
        FileShareSession.workspace_id == member.workspace_id
    )
    statement = repo.apply_sorting(statement, sorting)
    results, count = await repo.paginate(
        statement, limit=pagination.limit, page=pagination.page
    )
    return list(results), count


async def get_session(
    session: AsyncReadSession,
    auth_subject: AuthPrincipal[Subject],
    *,
    session_id: UUID4,
) -> FileShareSession | None:
    """Get a file sharing session by ID, verifying workspace membership."""
    if not is_member_principal(auth_subject):
        return None

    member = auth_subject.subject
    repo = FileShareSessionRepository.from_session(session)
    fs_session = await repo.get_by_id(session_id)
    if fs_session is None or fs_session.workspace_id != member.workspace_id:
        return None
    return fs_session


async def list_session_downloads(
    session: AsyncReadSession,
    auth_subject: AuthPrincipal[Subject],
    *,
    session_id: UUID4,
) -> list[FileShareDownload]:
    """List downloads for a file sharing session."""
    fs_session = await get_session(session, auth_subject, session_id=session_id)
    if fs_session is None:
        return []

    download_repo = FileShareDownloadRepository.from_session(session)
    return await download_repo.get_by_session_id(session_id)


async def list_session_payments(
    session: AsyncReadSession,
    auth_subject: AuthPrincipal[Subject],
    *,
    session_id: UUID4,
) -> list[FileSharePayment]:
    """List payments for a file sharing session."""
    fs_session = await get_session(session, auth_subject, session_id=session_id)
    if fs_session is None:
        return []

    payment_repo = FileSharePaymentRepository.from_session(session)
    return await payment_repo.get_by_session_id(session_id)
