"""Payment persistence layer with workspace-scoped queries.

``PaymentRepository`` handles paginated listing, ID look-up, and
Stripe charge-ID association for payment records.
"""

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import Select, select

from rapidly.core.queries import (
    Options,
    Repository,
    SoftDeleteByIdMixin,
    SoftDeleteMixin,
    SortableMixin,
    SortingClause,
)
from rapidly.enums import PaymentProcessor
from rapidly.identity.auth.models import (
    AuthPrincipal,
    User,
    Workspace,
    is_user_principal,
    is_workspace_principal,
)
from rapidly.models import Payment, WorkspaceMembership

from .ordering import PaymentSortProperty


class PaymentRepository(
    SortableMixin[Payment, PaymentSortProperty],
    SoftDeleteByIdMixin[Payment, UUID],
    SoftDeleteMixin[Payment],
    Repository[Payment],
):
    """Payment queries with Stripe charge-id lookups and workspace scoping."""

    model = Payment

    async def get_by_processor_id(
        self, processor: PaymentProcessor, processor_id: str, *, options: Options = ()
    ) -> Payment | None:
        statement = (
            self.get_base_statement()
            .where(Payment.processor == processor, Payment.processor_id == processor_id)
            .options(*options)
        )
        return await self.get_one_or_none(statement)

    def apply_list_filters(
        self,
        stmt: Select[tuple[Payment]],
        *,
        workspace_id: Sequence[UUID] | None = None,
        status: Sequence[str] | None = None,
        method: Sequence[str] | None = None,
        customer_email: Sequence[str] | None = None,
    ) -> Select[tuple[Payment]]:
        if workspace_id is not None:
            stmt = stmt.where(Payment.workspace_id.in_(workspace_id))
        if status is not None:
            stmt = stmt.where(Payment.status.in_(status))
        if method is not None:
            stmt = stmt.where(Payment.method.in_(method))
        if customer_email is not None:
            stmt = stmt.where(Payment.customer_email.in_(customer_email))
        return stmt

    def get_readable_statement(
        self, auth_subject: AuthPrincipal[User | Workspace]
    ) -> Select[tuple[Payment]]:
        statement = self.get_base_statement()

        if is_user_principal(auth_subject):
            user = auth_subject.subject
            statement = statement.where(
                Payment.workspace_id.in_(
                    select(WorkspaceMembership.workspace_id).where(
                        WorkspaceMembership.user_id == user.id,
                        WorkspaceMembership.deleted_at.is_(None),
                    )
                )
            )
        elif is_workspace_principal(auth_subject):
            statement = statement.where(
                Payment.workspace_id == auth_subject.subject.id,
            )

        return statement

    def get_sorting_clause(self, property: PaymentSortProperty) -> SortingClause:
        match property:
            case PaymentSortProperty.created_at:
                return Payment.created_at
            case PaymentSortProperty.status:
                return Payment.status
            case PaymentSortProperty.amount:
                return Payment.amount
            case PaymentSortProperty.method:
                return Payment.method
