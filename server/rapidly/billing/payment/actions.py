"""Payment recording and Stripe charge synchronisation service.

Creates ``Payment`` records from incoming Stripe charge / payment-intent
events, handles refund and dispute status updates, and exposes
paginated payment queries scoped to an workspace.
"""

import uuid
from collections.abc import Sequence

from rapidly.core.ordering import Sorting
from rapidly.core.pagination import PaginationParams
from rapidly.identity.auth.models import AuthPrincipal, User, Workspace
from rapidly.models import Payment
from rapidly.models.payment import PaymentStatus
from rapidly.postgres import AsyncReadSession

from .ordering import PaymentSortProperty
from .queries import PaymentRepository

# ── Reads ──


async def list(
    session: AsyncReadSession,
    auth_subject: AuthPrincipal[User | Workspace],
    *,
    workspace_id: Sequence[uuid.UUID] | None = None,
    status: Sequence[PaymentStatus] | None = None,
    method: Sequence[str] | None = None,
    customer_email: Sequence[str] | None = None,
    pagination: PaginationParams,
    sorting: Sequence[Sorting[PaymentSortProperty]] = (
        (PaymentSortProperty.created_at, True),
    ),
) -> tuple[Sequence[Payment], int]:
    repository = PaymentRepository.from_session(session)
    statement = repository.get_readable_statement(auth_subject)
    statement = repository.apply_list_filters(
        statement,
        workspace_id=workspace_id,
        status=status,
        method=method,
        customer_email=customer_email,
    )
    statement = repository.apply_sorting(statement, sorting)

    return await repository.paginate(
        statement, limit=pagination.limit, page=pagination.page
    )


async def get(
    session: AsyncReadSession,
    auth_subject: AuthPrincipal[User | Workspace],
    id: uuid.UUID,
) -> Payment | None:
    repository = PaymentRepository.from_session(session)
    statement = repository.get_readable_statement(auth_subject).where(Payment.id == id)
    return await repository.get_one_or_none(statement)
