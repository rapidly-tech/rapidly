"""Member persistence layer with workspace-scoped queries.

``MemberRepository`` handles CRUD for members within an workspace,
including external-ID look-up, email-based search, and eager-loading
of related customer associations.
"""

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import Select, asc, desc, func, select
from sqlalchemy.orm import joinedload

from rapidly.core.queries import (
    Repository,
    SoftDeleteByIdMixin,
    SoftDeleteMixin,
)
from rapidly.identity.auth.models import (
    AuthPrincipal,
    User,
    Workspace,
    is_user_principal,
    is_workspace_principal,
)
from rapidly.models.customer import Customer
from rapidly.models.member import Member, MemberRole
from rapidly.models.workspace_membership import WorkspaceMembership
from rapidly.postgres import AsyncReadSession, AsyncSession


class MemberRepository(
    SoftDeleteByIdMixin[Member, UUID],
    SoftDeleteMixin[Member],
    Repository[Member],
):
    """Member queries scoped by customer, with email-based lookups."""

    model = Member

    # ── Email lookups ──

    async def get_by_customer_and_email(
        self,
        session: AsyncSession | None = None,
        customer: Customer | None = None,
        email: str | None = None,
        *,
        customer_id: UUID | None = None,
    ) -> Member | None:
        """
        Get a member by customer and email.

        Accepts either a ``customer`` object or a ``customer_id``.
        The ``session`` parameter is accepted for backward compatibility
        but ignored — the repository's own session is always used.

        Returns:
            Member if found, None otherwise
        """
        cid = customer_id or (customer.id if customer else None)
        if cid is None:
            raise ValueError("Either customer or customer_id must be provided")
        email = email or (customer.email if customer else None)
        if email is None:
            raise ValueError("email must be provided when customer is not given")
        statement = select(Member).where(
            Member.customer_id == cid,
            Member.email == email,
            Member.deleted_at.is_(None),
        )
        return await self.get_one_or_none(statement)

    async def get_by_customer_id_and_email(
        self,
        customer_id: UUID,
        email: str,
    ) -> Member | None:
        """
        Get a member by customer ID and email.

        Returns:
            Member if found, None otherwise
        """
        statement = select(Member).where(
            Member.customer_id == customer_id,
            Member.email == email,
            Member.deleted_at.is_(None),
        )
        return await self.get_one_or_none(statement)

    # ── Reads ──

    async def get_by_customer_id_and_external_id(
        self,
        customer_id: UUID,
        external_id: str,
    ) -> Member | None:
        """
        Get a member by customer ID and external ID.

        Returns:
            Member if found, None otherwise
        """
        statement = select(Member).where(
            Member.customer_id == customer_id,
            Member.external_id == external_id,
            Member.deleted_at.is_(None),
        )
        return await self.get_one_or_none(statement)

    async def get_by_id_and_customer_id(
        self,
        member_id: UUID,
        customer_id: UUID,
    ) -> Member | None:
        """
        Get a member by ID and customer ID.

        Returns:
            Member if found, None otherwise
        """
        statement = select(Member).where(
            Member.id == member_id,
            Member.customer_id == customer_id,
            Member.deleted_at.is_(None),
        )
        return await self.get_one_or_none(statement)

    async def list_by_customer(
        self,
        session: AsyncReadSession | None = None,
        customer_id: UUID | None = None,
    ) -> Sequence[Member]:
        """List members for a customer.

        The ``session`` parameter is accepted for backward compatibility
        but ignored — the repository's own session is always used.
        """
        if customer_id is None:
            raise ValueError("customer_id must be provided")
        statement = select(Member).where(
            Member.customer_id == customer_id,
            Member.deleted_at.is_(None),
        )
        return await self.get_all(statement)

    async def get_owner_by_customer_id(
        self,
        session: AsyncReadSession | None = None,
        customer_id: UUID | None = None,
    ) -> Member | None:
        """Get the owner member for a customer.

        The ``session`` parameter is accepted for backward compatibility
        but ignored — the repository's own session is always used.
        """
        if customer_id is None:
            raise ValueError("customer_id must be provided")
        statement = (
            select(Member)
            .where(
                Member.customer_id == customer_id,
                Member.role == MemberRole.owner,
                Member.deleted_at.is_(None),
            )
            .options(joinedload(Member.customer).joinedload(Customer.workspace))
        )
        result = await self.session.execute(statement)
        return result.unique().scalar_one_or_none()

    async def list_by_email_and_workspace(
        self,
        email: str,
        workspace_id: UUID,
        include_deleted: bool = False,
    ) -> Sequence[Member]:
        """
        Get all members with the given email in the workspace.
        Used for customer portal email disambiguation when a user's email
        belongs to multiple customers.
        """
        statement = (
            select(Member)
            .where(
                func.lower(Member.email) == email.lower(),
                Member.workspace_id == workspace_id,
            )
            .options(joinedload(Member.customer))
        )
        if not include_deleted:
            statement = statement.where(Member.deleted_at.is_(None))
        result = await self.session.execute(statement)
        return result.scalars().unique().all()

    async def list_by_customers(
        self,
        session: AsyncReadSession | None = None,
        customer_ids: Sequence[UUID] = (),
    ) -> Sequence[Member]:
        """Get all members for multiple customers (batch loading to avoid N+1).

        The ``session`` parameter is accepted for backward compatibility
        but ignored — the repository's own session is always used.
        """
        if not customer_ids:
            return []

        statement = select(Member).where(
            Member.customer_id.in_(customer_ids),
            Member.deleted_at.is_(None),
        )
        return await self.get_all(statement)

    async def get_existing_ids(
        self,
        member_ids: set[UUID],
    ) -> set[UUID]:
        """Return the subset of member_ids that exist and are not deleted."""
        if not member_ids:
            return set()
        statement = select(Member.id).where(
            Member.deleted_at.is_(None),
            Member.id.in_(member_ids),
        )
        result = await self.session.execute(statement)
        return set(result.scalars().all())

    def apply_list_filters(
        self,
        stmt: Select[tuple[Member]],
        *,
        customer_id: UUID | None = None,
        external_customer_id: str | None = None,
        sorting: Sequence[tuple[str, bool]] = (),
    ) -> Select[tuple[Member]]:
        if customer_id is not None:
            stmt = stmt.where(Member.customer_id == customer_id)
        if external_customer_id is not None:
            stmt = stmt.join(Customer).where(
                Customer.external_id == external_customer_id
            )
        for criterion, is_desc in sorting:
            clause_fn = desc if is_desc else asc
            if criterion == "created_at":
                stmt = stmt.order_by(clause_fn(Member.created_at))
        return stmt

    def get_readable_statement(
        self, auth_subject: AuthPrincipal[User | Workspace]
    ) -> Select[tuple[Member]]:
        """Get a statement filtered by the auth subject's access to workspaces."""
        statement = self.get_base_statement()

        if is_user_principal(auth_subject):
            user = auth_subject.subject
            statement = statement.where(
                Member.workspace_id.in_(
                    select(WorkspaceMembership.workspace_id).where(
                        WorkspaceMembership.user_id == user.id,
                        WorkspaceMembership.deleted_at.is_(None),
                    )
                )
            )
        elif is_workspace_principal(auth_subject):
            statement = statement.where(
                Member.workspace_id == auth_subject.subject.id,
            )

        return statement
