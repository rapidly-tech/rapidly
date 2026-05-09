"""Customer persistence with webhook/event dispatch on every write operation."""

import contextlib
from collections.abc import AsyncGenerator, Sequence
from typing import Any
from uuid import UUID

from sqlalchemy import Select, asc, desc, func, or_, select
from sqlalchemy import inspect as orm_inspect
from sqlalchemy.orm import InstanceState

from rapidly.analytics.event.system import CustomerUpdatedFields, SystemEvent
from rapidly.core.address import Address
from rapidly.core.metadata import MetadataQuery, apply_metadata_clause
from rapidly.core.queries import (
    Options,
    Repository,
    SoftDeleteByIdMixin,
    SoftDeleteMixin,
)
from rapidly.core.queries.utils import escape_like
from rapidly.customers.customer.ordering import CustomerSortProperty
from rapidly.identity.auth.models import (
    AuthPrincipal,
    User,
    Workspace,
    is_user_principal,
    is_workspace_principal,
)
from rapidly.models import Customer, WorkspaceMembership
from rapidly.models.webhook_endpoint import WebhookEventType
from rapidly.worker import dispatch_task

# Fields whose changes are propagated via customer.updated events
_TRACKED_FIELDS: tuple[str, ...] = ("name", "email", "billing_address", "user_metadata")


def _attr_delta(state: InstanceState[Customer], attr_name: str) -> tuple[bool, Any]:
    """Return ``(changed, new_value)`` for a single attribute on *state*."""
    history = state.attrs[attr_name].history
    if not history.has_changes():
        return False, None

    old = history.deleted[0] if history.deleted else None
    new = history.added[0] if history.added else None
    return (old != new, new)


class CustomerRepository(
    SoftDeleteByIdMixin[Customer, UUID],
    SoftDeleteMixin[Customer],
    Repository[Customer],
):
    """Customer CRUD with automatic webhook + system-event dispatch."""

    model = Customer

    # ── Writes ────────────────────────────────────────────────────────

    async def create(self, object: Customer, *, flush: bool = False) -> Customer:
        customer = await super().create(object, flush=flush)
        if customer.id is None:
            customer.id = Customer.__table__.c.id.default.arg(None)
        return customer

    @contextlib.asynccontextmanager
    async def create_context(
        self, object: Customer, *, flush: bool = False
    ) -> AsyncGenerator[Customer]:
        customer = await self.create(object, flush=flush)
        yield customer
        assert customer.id is not None, "Customer.id must be set before dispatch"
        self._dispatch_lifecycle(
            customer.id, WebhookEventType.customer_created, SystemEvent.customer_created
        )

    async def update(
        self,
        object: Customer,
        *,
        update_dict: dict[str, Any] | None = None,
        flush: bool = False,
    ) -> Customer:
        state = orm_inspect(object)
        customer = await super().update(object, update_dict=update_dict, flush=flush)
        dispatch_task(
            "customer.webhook", WebhookEventType.customer_updated, customer.id
        )

        if not customer.deleted_at:
            fields = self._collect_field_changes(state)
            dispatch_task(
                "customer.event", customer.id, SystemEvent.customer_updated, fields
            )
        return customer

    async def soft_delete(self, object: Customer, *, flush: bool = False) -> Customer:
        customer = await super().soft_delete(object, flush=flush)
        self._archive_external_id(customer)
        self._dispatch_lifecycle(
            customer.id, WebhookEventType.customer_deleted, SystemEvent.customer_deleted
        )
        return customer

    # ── Private helpers ───────────────────────────────────────────────

    @staticmethod
    def _archive_external_id(customer: Customer) -> None:
        """Move external_id into user_metadata so the slot can be reused."""
        if customer.external_id:
            meta = customer.user_metadata
            meta["__external_id"] = customer.external_id
            customer.user_metadata = meta
            customer.external_id = None

    @staticmethod
    def _dispatch_lifecycle(
        customer_id: UUID,
        webhook_type: WebhookEventType,
        event: SystemEvent,
    ) -> None:
        dispatch_task("customer.webhook", webhook_type, customer_id)
        dispatch_task("customer.event", customer_id, event)

    @staticmethod
    def _collect_field_changes(state: InstanceState[Customer]) -> CustomerUpdatedFields:
        """Build a dict of changed fields from the ORM inspection state."""
        fields: CustomerUpdatedFields = {}

        changed, val = _attr_delta(state, "name")
        if changed:
            fields["name"] = val

        changed, val = _attr_delta(state, "email")
        if changed:
            fields["email"] = val

        changed, val = _attr_delta(state, "billing_address")
        if changed:
            fields["billing_address"] = (
                None if val is None else Address.model_validate(val).to_dict()
            )

        changed, val = _attr_delta(state, "user_metadata")
        if changed:
            fields["metadata"] = val

        return fields

    async def get_by_id_and_workspace(
        self, id: UUID, workspace_id: UUID
    ) -> Customer | None:
        statement = self.get_base_statement().where(
            Customer.id == id, Customer.workspace_id == workspace_id
        )
        return await self.get_one_or_none(statement)

    async def get_by_email_and_workspace(
        self, email: str, workspace_id: UUID
    ) -> Customer | None:
        statement = self.get_base_statement().where(
            func.lower(Customer.email) == email.lower(),
            Customer.workspace_id == workspace_id,
        )
        return await self.get_one_or_none(statement)

    async def get_by_external_id_and_workspace(
        self, external_id: str, workspace_id: UUID
    ) -> Customer | None:
        statement = self.get_base_statement().where(
            Customer.external_id == external_id,
            Customer.workspace_id == workspace_id,
        )
        return await self.get_one_or_none(statement)

    async def stream_by_workspace(
        self,
        auth_subject: AuthPrincipal[User | Workspace],
        workspace_id: Sequence[UUID] | None,
    ) -> AsyncGenerator[Customer]:
        statement = self.get_readable_statement(auth_subject)

        if workspace_id is not None:
            statement = statement.where(
                Customer.workspace_id.in_(workspace_id),
            )

        async for customer in self.stream(statement):
            yield customer

    async def get_readable_by_id(
        self,
        auth_subject: AuthPrincipal[User | Workspace],
        id: UUID,
        *,
        options: Options = (),
    ) -> Customer | None:
        statement = (
            self.get_readable_statement(auth_subject)
            .where(Customer.id == id)
            .options(*options)
        )
        return await self.get_one_or_none(statement)

    def apply_list_filters(
        self,
        stmt: Select[tuple[Customer]],
        *,
        workspace_id: Sequence[UUID] | None = None,
        email: str | None = None,
        metadata: MetadataQuery | None = None,
        query: str | None = None,
        sorting: Sequence[tuple[CustomerSortProperty, bool]] = (),
    ) -> Select[tuple[Customer]]:
        if workspace_id is not None:
            stmt = stmt.where(Customer.workspace_id.in_(workspace_id))
        if email is not None:
            stmt = stmt.where(func.lower(Customer.email) == email.lower())
        if metadata is not None:
            stmt = apply_metadata_clause(Customer, stmt, metadata)
        if query is not None:
            escaped = escape_like(query)
            stmt = stmt.where(
                or_(
                    Customer.email.ilike(f"%{escaped}%"),
                    Customer.name.ilike(f"%{escaped}%"),
                    Customer.external_id.ilike(f"{escaped}%"),
                )
            )
        for criterion, is_desc in sorting:
            clause_fn = desc if is_desc else asc
            match criterion:
                case CustomerSortProperty.created_at:
                    stmt = stmt.order_by(clause_fn(Customer.created_at))
                case CustomerSortProperty.email:
                    stmt = stmt.order_by(clause_fn(Customer.email))
                case CustomerSortProperty.customer_name:
                    stmt = stmt.order_by(clause_fn(Customer.name))
        return stmt

    def get_readable_statement(
        self, auth_subject: AuthPrincipal[User | Workspace]
    ) -> Select[tuple[Customer]]:
        statement = self.get_base_statement()

        if is_user_principal(auth_subject):
            user = auth_subject.subject
            statement = statement.where(
                Customer.workspace_id.in_(
                    select(WorkspaceMembership.workspace_id).where(
                        WorkspaceMembership.user_id == user.id,
                        WorkspaceMembership.deleted_at.is_(None),
                    )
                )
            )
        elif is_workspace_principal(auth_subject):
            statement = statement.where(
                Customer.workspace_id == auth_subject.subject.id,
            )

        return statement
