"""Webhook persistence layer: endpoints, events, and delivery records.

``WebhookEndpointRepository`` manages webhook endpoint CRUD scoped to
an workspace.  ``WebhookEventRepository`` tracks the per-event
delivery lifecycle, and ``WebhookDeliveryRepository`` stores individual
HTTP attempt results for retry and audit purposes.
"""

from collections.abc import Sequence
from datetime import datetime
from typing import Literal, cast
from uuid import UUID

from sqlalchemy import CursorResult, Select, String, func, or_, select, update
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import contains_eager, joinedload
from sqlalchemy.sql.expression import cast as sql_cast

from rapidly.core.queries import (
    Options,
    Repository,
    SoftDeleteByIdMixin,
    SoftDeleteMixin,
)
from rapidly.core.queries.utils import escape_like
from rapidly.identity.auth.models import (
    AuthPrincipal,
    is_user_principal,
    is_workspace_principal,
)
from rapidly.models import (
    User,
    WebhookDelivery,
    WebhookEndpoint,
    WebhookEvent,
    Workspace,
    WorkspaceMembership,
)
from rapidly.models.webhook_endpoint import WebhookEventType


class WebhookEventRepository(
    SoftDeleteByIdMixin[WebhookEvent, UUID],
    SoftDeleteMixin[WebhookEvent],
    Repository[WebhookEvent],
):
    """Webhook event persistence with payload-type filtering and endpoint joins."""

    model = WebhookEvent

    # ── Reads ──

    async def get_all_undelivered(
        self,
        older_than: datetime | None = None,
        *,
        limit: int = 1000,
    ) -> Sequence[WebhookEvent]:
        statement = (
            self.get_base_statement()
            .join(
                WebhookDelivery,
                WebhookDelivery.webhook_event_id == WebhookEvent.id,
                isouter=True,
            )
            .where(
                WebhookDelivery.id.is_(None),
                WebhookEvent.payload.is_not(None),
                WebhookEvent.skipped.is_(False),
            )
        )
        if older_than is not None:
            statement = statement.where(WebhookEvent.created_at < older_than)
        statement = statement.limit(limit)
        return await self.get_all(statement)

    async def get_recent_by_endpoint(
        self, endpoint_id: UUID, *, limit: int
    ) -> Sequence[WebhookEvent]:
        """
        Get recent completed events for an endpoint.

        Returns a list of WebhookEvent objects ordered by
        created_at descending (most recent first).

        Only includes events where succeeded is not NULL (completed events),
        excluding pending events that are still being retried.
        """
        statement = (
            self.get_base_statement()
            .where(
                WebhookEvent.webhook_endpoint_id == endpoint_id,
                WebhookEvent.succeeded.is_not(None),
            )
            .order_by(WebhookEvent.created_at.desc())
            .limit(limit)
        )
        return await self.get_all(statement)

    async def get_pending_by_endpoint(
        self, endpoint_id: UUID
    ) -> Sequence[WebhookEvent]:
        """
        Get all pending events for an endpoint.

        Returns events where succeeded is NULL (still being retried).
        """
        statement = self.get_base_statement().where(
            WebhookEvent.webhook_endpoint_id == endpoint_id,
            WebhookEvent.succeeded.is_(None),
            WebhookEvent.skipped.is_(False),
        )
        return await self.get_all(statement)

    def get_readable_statement(
        self, auth_subject: AuthPrincipal[User | Workspace]
    ) -> Select[tuple[WebhookEvent]]:
        statement = (
            self.get_base_statement()
            .join(
                WebhookEndpoint, WebhookEvent.webhook_endpoint_id == WebhookEndpoint.id
            )
            .options(contains_eager(WebhookEvent.webhook_endpoint))
        )

        if is_user_principal(auth_subject):
            user = auth_subject.subject
            statement = statement.where(
                WebhookEndpoint.workspace_id.in_(
                    select(WorkspaceMembership.workspace_id).where(
                        WorkspaceMembership.user_id == user.id,
                        WorkspaceMembership.deleted_at.is_(None),
                    )
                )
            )
        elif is_workspace_principal(auth_subject):
            statement = statement.where(
                WebhookEndpoint.workspace_id == auth_subject.subject.id
            )

        return statement

    def get_eager_options(self) -> Options:
        return (joinedload(WebhookEvent.webhook_endpoint),)

    async def count_undelivered_older_than(
        self,
        endpoint_id: UUID,
        event_id: UUID,
        before: datetime,
        age_limit: datetime,
    ) -> int:
        """Count undelivered events for an endpoint older than the given event
        but newer than the age limit."""
        statement = (
            select(func.count(WebhookEvent.id))
            .join(
                WebhookDelivery,
                WebhookDelivery.webhook_event_id == WebhookEvent.id,
                isouter=True,
            )
            .where(
                WebhookEvent.deleted_at.is_(None),
                WebhookEvent.webhook_endpoint_id == endpoint_id,
                WebhookEvent.id != event_id,
                WebhookDelivery.id.is_(None),
                WebhookEvent.created_at < before,
                WebhookEvent.created_at >= age_limit,
            )
            .limit(1)
        )
        res = await self.session.execute(statement)
        return res.scalar_one()

    async def skip_pending_by_endpoint(self, endpoint_id: UUID) -> int:
        """Bulk-update all pending events for an endpoint to skipped=True.

        Returns the number of rows updated.
        """
        statement = (
            update(WebhookEvent)
            .where(
                WebhookEvent.webhook_endpoint_id == endpoint_id,
                WebhookEvent.succeeded.is_(None),
                WebhookEvent.skipped.is_(False),
                WebhookEvent.deleted_at.is_(None),
            )
            .values(skipped=True)
        )
        result = cast(CursorResult[WebhookEvent], await self.session.execute(statement))
        return result.rowcount

    async def archive_payloads(
        self,
        older_than: datetime,
        batch_size: int,
    ) -> int:
        """Null-out payloads for events older than the cutoff.

        Returns the number of rows updated in this batch.
        """
        batch_subquery = (
            select(WebhookEvent.id)
            .where(
                WebhookEvent.created_at < older_than,
                WebhookEvent.payload.is_not(None),
            )
            .order_by(WebhookEvent.created_at.asc())
            .limit(batch_size)
        )
        statement = (
            update(WebhookEvent)
            .where(WebhookEvent.id.in_(batch_subquery))
            .values(payload=None)
        )
        result = cast(CursorResult[WebhookEvent], await self.session.execute(statement))
        return result.rowcount


class WebhookDeliveryRepository(
    SoftDeleteByIdMixin[WebhookDelivery, UUID],
    SoftDeleteMixin[WebhookDelivery],
    Repository[WebhookDelivery],
):
    """Delivery-attempt records with HTTP status and retry tracking."""

    model = WebhookDelivery

    # ── Reads ──

    async def get_all_by_event(self, event: UUID) -> Sequence[WebhookDelivery]:
        statement = (
            self.get_base_statement()
            .where(WebhookDelivery.webhook_event_id == event)
            .order_by(WebhookDelivery.created_at.asc())
        )
        return await self.get_all(statement)

    def apply_list_filters(
        self,
        stmt: Select[tuple[WebhookDelivery]],
        *,
        endpoint_id: Sequence[UUID] | None = None,
        start_timestamp: datetime | None = None,
        end_timestamp: datetime | None = None,
        succeeded: bool | None = None,
        query: str | None = None,
        http_code_class: Literal["2xx", "3xx", "4xx", "5xx"] | None = None,
        event_type: Sequence[WebhookEventType] | None = None,
    ) -> Select[tuple[WebhookDelivery]]:
        if endpoint_id is not None:
            stmt = stmt.where(WebhookDelivery.webhook_endpoint_id.in_(endpoint_id))
        if start_timestamp is not None:
            stmt = stmt.where(WebhookDelivery.created_at > start_timestamp)
        if end_timestamp is not None:
            stmt = stmt.where(WebhookDelivery.created_at < end_timestamp)
        if succeeded is not None:
            stmt = stmt.where(WebhookDelivery.succeeded == succeeded)
        if query is not None:
            escaped = escape_like(query)
            stmt = stmt.where(
                or_(
                    sql_cast(WebhookDelivery.id, String).ilike(f"%{escaped}%"),
                    sql_cast(WebhookDelivery.webhook_event_id, String).ilike(
                        f"%{escaped}%"
                    ),
                    sql_cast(WebhookDelivery.http_code, String).ilike(f"%{escaped}%"),
                )
            )
        if http_code_class is not None:
            base = int(http_code_class[0]) * 100
            stmt = stmt.where(
                WebhookDelivery.http_code >= base,
                WebhookDelivery.http_code < base + 100,
            )
        if event_type is not None:
            stmt = stmt.join(
                WebhookEvent, WebhookDelivery.webhook_event_id == WebhookEvent.id
            ).where(WebhookEvent.type.in_(event_type))
        return stmt

    def get_readable_statement(
        self, auth_subject: AuthPrincipal[User | Workspace]
    ) -> Select[tuple[WebhookDelivery]]:
        statement = (
            self.get_base_statement()
            .join(
                WebhookEndpoint,
                WebhookDelivery.webhook_endpoint_id == WebhookEndpoint.id,
            )
            .options(contains_eager(WebhookDelivery.webhook_endpoint))
        )

        if is_user_principal(auth_subject):
            user = auth_subject.subject
            statement = statement.where(
                WebhookEndpoint.workspace_id.in_(
                    select(WorkspaceMembership.workspace_id).where(
                        WorkspaceMembership.user_id == user.id,
                        WorkspaceMembership.deleted_at.is_(None),
                    )
                )
            )
        elif is_workspace_principal(auth_subject):
            statement = statement.where(
                WebhookEndpoint.workspace_id == auth_subject.subject.id
            )

        return statement


class WebhookEndpointRepository(
    SoftDeleteByIdMixin[WebhookEndpoint, UUID],
    SoftDeleteMixin[WebhookEndpoint],
    Repository[WebhookEndpoint],
):
    """Webhook endpoint CRUD with event-type subscription filtering."""

    model = WebhookEndpoint

    # ── Filters ──

    def apply_list_filters(
        self,
        stmt: Select[tuple[WebhookEndpoint]],
        *,
        workspace_id: Sequence[UUID] | None = None,
    ) -> Select[tuple[WebhookEndpoint]]:
        if workspace_id is not None:
            stmt = stmt.where(WebhookEndpoint.workspace_id.in_(workspace_id))
        return stmt

    # ── Reads ──

    def get_readable_statement(
        self, auth_subject: AuthPrincipal[User | Workspace]
    ) -> Select[tuple[WebhookEndpoint]]:
        statement = self.get_base_statement()

        if is_user_principal(auth_subject):
            user = auth_subject.subject
            statement = statement.where(
                WebhookEndpoint.workspace_id.in_(
                    select(WorkspaceMembership.workspace_id).where(
                        WorkspaceMembership.user_id == user.id,
                        WorkspaceMembership.deleted_at.is_(None),
                    )
                )
            )
        elif is_workspace_principal(auth_subject):
            statement = statement.where(
                WebhookEndpoint.workspace_id == auth_subject.subject.id
            )

        return statement

    async def get_active_for_event(
        self,
        event: WebhookEventType,
        workspace_id: UUID,
    ) -> Sequence[WebhookEndpoint]:
        """Return enabled endpoints for a workspace that subscribe to the given event."""
        statement = select(WebhookEndpoint).where(
            WebhookEndpoint.deleted_at.is_(None),
            WebhookEndpoint.enabled.is_(True),
            WebhookEndpoint.events.bool_op("@>")(
                sql_cast(func.jsonb_build_array(event.value), JSONB)
            ),
            WebhookEndpoint.workspace_id == workspace_id,
        )
        res = await self.session.execute(statement)
        return res.scalars().unique().all()
