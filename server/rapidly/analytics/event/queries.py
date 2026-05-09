"""Event persistence layer with closure-table traversal and time-series aggregation.

``EventRepository`` provides cursor-based pagination, customer/member
association resolution, hierarchical sub-event retrieval via the closure
table, and time-bucketed statistics (hourly / daily / weekly / monthly /
yearly).
"""

import re
from collections.abc import Sequence
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import (
    CTE,
    ColumnElement,
    Numeric,
    Select,
    String,
    UnaryExpression,
    and_,
    asc,
    case,
    cast,
    desc,
    func,
    literal_column,
    or_,
    select,
    text,
)
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import aliased, joinedload

from rapidly.core.ordering import Sorting
from rapidly.core.queries import FindByIdMixin, Repository
from rapidly.core.queries.base import Options
from rapidly.core.time_queries import TimeInterval
from rapidly.core.utils import create_uuid
from rapidly.identity.auth.models import (
    AuthPrincipal,
    User,
    Workspace,
    is_user_principal,
    is_workspace_principal,
)
from rapidly.models import (
    Customer,
    Event,
    EventType,
    WorkspaceMembership,
)
from rapidly.models.event import EventClosure, EventSource

from .ordering import EventSortProperty

# Strict allowlist regex for aggregate field names used in SQL text() expressions.
# Only lowercase letters, digits, underscores, and dots are permitted.
_SAFE_FIELD_RE = re.compile(r"^[a-z_][a-z0-9_.]{0,50}$")


def _validate_aggregate_fields(fields: Sequence[str]) -> None:
    """Defense-in-depth validation for aggregate field names before SQL interpolation.

    The API layer has its own allowlist; this is a secondary guard at the
    repository level to prevent SQL injection if the API allowlist is ever
    loosened or bypassed.
    """
    for field in fields:
        if not _SAFE_FIELD_RE.match(field):
            raise ValueError(f"Invalid aggregate field: {field!r}")


class EventRepository(Repository[Event], FindByIdMixin[Event, UUID]):
    """Time-series event queries, closure-table traversal, and statistical aggregation."""

    model = Event

    # ------------------------------------------------------------------
    # Eager-loading options
    # ------------------------------------------------------------------

    def get_eager_options(self) -> Options:
        return (joinedload(Event.customer), joinedload(Event.event_types))

    # ------------------------------------------------------------------
    # Filter clause builders
    # ------------------------------------------------------------------

    def get_customer_id_filter_clause(
        self, customer_id: Sequence[UUID]
    ) -> ColumnElement[bool]:
        return or_(
            Event.customer_id.in_(customer_id),
            Event.external_customer_id.in_(
                select(Customer.external_id).where(Customer.id.in_(customer_id))
            ),
        )

    def get_external_customer_id_filter_clause(
        self, external_customer_id: Sequence[str]
    ) -> ColumnElement[bool]:
        return or_(
            Event.external_customer_id.in_(external_customer_id),
            Event.customer_id.in_(
                select(Customer.id).where(
                    Customer.external_id.in_(external_customer_id)
                )
            ),
        )

    # ------------------------------------------------------------------
    # Access-controlled statements
    # ------------------------------------------------------------------

    def get_readable_statement(
        self, auth_subject: AuthPrincipal[User | Workspace]
    ) -> Select[tuple[Event]]:
        stmt = self.get_base_statement()

        if is_user_principal(auth_subject):
            member_user = auth_subject.subject
            stmt = stmt.where(
                Event.workspace_id.in_(
                    select(WorkspaceMembership.workspace_id).where(
                        WorkspaceMembership.user_id == member_user.id,
                        WorkspaceMembership.deleted_at.is_(None),
                    )
                )
            )

        elif is_workspace_principal(auth_subject):
            stmt = stmt.where(Event.workspace_id == auth_subject.subject.id)

        return stmt

    def get_customer_text_search_clause(
        self, escaped_query: str
    ) -> ColumnElement[bool]:
        """Build a subquery matching customers by ID, external_id, name, or email."""
        return Event.customer_id.in_(
            select(Customer.id).where(
                or_(
                    cast(Customer.id, String).ilike(f"%{escaped_query}%"),
                    Customer.external_id.ilike(f"%{escaped_query}%"),
                    Customer.name.ilike(f"%{escaped_query}%"),
                    Customer.email.ilike(f"%{escaped_query}%"),
                )
            )
        )

    def get_event_names_statement(
        self, auth_subject: AuthPrincipal[User | Workspace]
    ) -> Select[tuple[str, EventSource, int, datetime, datetime]]:
        return (
            self.get_readable_statement(auth_subject)
            .with_only_columns(
                Event.name,
                Event.source,
                func.count(Event.id).label("occurrences"),
                func.min(Event.timestamp).label("first_seen"),
                func.max(Event.timestamp).label("last_seen"),
            )
            .group_by(Event.name, Event.source)
        )

    # ------------------------------------------------------------------
    # Simple reads
    # ------------------------------------------------------------------

    async def get_all_by_workspace(self, workspace_id: UUID) -> Sequence[Event]:
        stmt = self.get_base_statement().where(Event.workspace_id == workspace_id)
        return await self.get_all(stmt)

    # ------------------------------------------------------------------
    # Batch insert
    # ------------------------------------------------------------------

    async def insert_batch(
        self, events: Sequence[dict[str, Any]]
    ) -> tuple[Sequence[UUID], int]:
        if not events:
            return [], 0

        orphaned_children: list[dict[str, Any]] = []

        for evt in events:
            if evt.get("root_id") is not None:
                continue
            if evt.get("parent_id") is None:
                if evt.get("id") is None:
                    evt["id"] = create_uuid()
                evt["root_id"] = evt["id"]
            else:
                orphaned_children.append(evt)

        # Resolve root_id from parent for orphaned child events
        if orphaned_children:
            parent_ids = {e["parent_id"] for e in orphaned_children}
            rows = await self.session.execute(
                select(Event.id, Event.root_id).where(Event.id.in_(parent_ids))
            )
            root_lookup = {pid: rid or pid for pid, rid in rows}
            for evt in orphaned_children:
                pid = evt["parent_id"]
                evt["root_id"] = root_lookup.get(pid, pid)

        stmt = (
            insert(Event)
            .on_conflict_do_nothing(index_elements=["external_id"])
            .returning(Event.id)
        )
        result = await self.session.execute(stmt, events)
        new_ids = [row[0] for row in result.all()]

        duplicate_count = len(events) - len(new_ids)

        return new_ids, duplicate_count

    # ------------------------------------------------------------------
    # Single-event aggregation
    # ------------------------------------------------------------------

    async def get_with_aggregation(
        self,
        auth_subject: AuthPrincipal[User | Workspace],
        id: UUID,
        aggregate_fields: Sequence[str],
    ) -> Event | None:
        """Fetch one event with descendant-aggregated metadata."""
        stmt = self.get_readable_statement(auth_subject).where(Event.id == id)

        events, _ = await self.list_with_closure_table(
            stmt, limit=1, page=1, aggregate_fields=aggregate_fields
        )

        return events[0] if events else None

    # ------------------------------------------------------------------
    # Closure-table listing
    # ------------------------------------------------------------------

    async def list_with_closure_table(
        self,
        statement: Select[tuple[Event]],
        limit: int,
        page: int,
        aggregate_fields: Sequence[str] = (),
        depth: int | None = None,
        parent_id: UUID | None = None,
        cursor_pagination: bool = False,
        sorting: Sequence[Sorting[EventSortProperty]] = (
            (EventSortProperty.timestamp, True),
        ),
    ) -> tuple[Sequence[Event], int]:
        """List events using the closure table for correct descendant counts.

        Optionally aggregates numeric metadata fields from descendants.

        Depth semantics:
          - ``None``: no hierarchy filtering (all matching events)
          - ``0``: root events only (or nothing if parent_id specified)
          - ``1``: roots + direct children
          - ``N``: roots + descendants up to N levels

        When ``parent_id`` is set, descendants of that event are returned
        (excluding the parent itself).  Otherwise root events serve as
        anchors and are included.

        Returns ``(events, 1_if_has_next_page | 0)`` for cursor pagination,
        or ``(events, total_count)`` for offset pagination.

        Raises ``ValueError`` if any aggregate field fails the allowlist check
        (defense-in-depth — the API layer also validates).
        """
        _validate_aggregate_fields(aggregate_fields)
        # Depth filtering via closure table
        if depth is not None:
            if parent_id is not None:
                anchor_set = select(Event.id).where(Event.id == parent_id)
                descendant_ids = select(EventClosure.descendant_id).where(
                    EventClosure.ancestor_id.in_(anchor_set),
                    EventClosure.depth > 0,
                    EventClosure.depth <= depth,
                )
            else:
                anchor_set = statement.with_only_columns(Event.id).where(
                    Event.parent_id.is_(None)
                )
                descendant_ids = select(EventClosure.descendant_id).where(
                    EventClosure.ancestor_id.in_(anchor_set),
                    EventClosure.depth <= depth,
                )

            statement = statement.where(Event.id.in_(descendant_ids))

        child_alias = aliased(Event, name="descendant_event")

        # Paginate
        row_offset = (page - 1) * limit
        fetch_limit = limit + 1 if cursor_pagination else limit

        page_subq = (statement.limit(fetch_limit).offset(row_offset)).subquery(
            "paginated_events"
        )

        # Build aggregation columns
        agg_cols: list[Any] = [
            EventClosure.ancestor_id,
            (func.count() - 1).label("descendant_count"),
        ]

        agg_labels: dict[str, str] = {}
        for field in aggregate_fields:
            pg_path = "{" + field.replace(".", ",") + "}"
            col_label = f"agg_{field.replace('.', '_')}"

            numeric_val = cast(
                child_alias.user_metadata.op("#>>")(literal_column(f"'{pg_path}'")),
                Numeric,
            )

            agg_cols.append(func.sum(numeric_val).label(col_label))
            agg_labels[field] = col_label

        page_id_col = page_subq.c.id

        lateral_agg = (
            select(*agg_cols)
            .select_from(EventClosure)
            .join(child_alias, EventClosure.descendant_id == child_alias.id)
            .where(EventClosure.ancestor_id == page_id_col)
            .group_by(EventClosure.ancestor_id)
        ).lateral("aggregations")

        # Build metadata expression with merged aggregations
        meta_ref = page_subq.c.user_metadata
        meta_expr: Any = meta_ref
        if aggregate_fields:
            for field, col_label in agg_labels.items():
                segments = field.split(".")
                pg_path = "{" + ",".join(segments) + "}"
                agg_val = getattr(lateral_agg.c, col_label)

                if len(segments) > 1:
                    nested = func.to_jsonb(agg_val)
                    for seg in reversed(segments):
                        nested = func.jsonb_build_object(seg, nested)

                    top_key = segments[0]
                    existing = func.coalesce(
                        meta_expr.op("->")(top_key), text("'{}'::jsonb")
                    )
                    merged = existing.op("||")(nested.op("->")(top_key))

                    meta_expr = func.jsonb_set(
                        meta_expr,
                        text(f"'{{{top_key}}}'"),
                        merged,
                        text("true"),
                    )
                else:
                    meta_expr = func.jsonb_set(
                        meta_expr,
                        text(f"'{pg_path}'"),
                        func.to_jsonb(agg_val),
                        text("true"),
                    )

        # Sort
        order_clauses: list[UnaryExpression[Any]] = []
        for prop, is_descending in sorting:
            direction_fn = desc if is_descending else asc
            if prop == EventSortProperty.timestamp:
                order_clauses.append(direction_fn(page_subq.c.timestamp))

        final = (
            select(Event)
            .select_from(page_subq)
            .join(Event, Event.id == page_subq.c.id)
            .add_columns(
                func.coalesce(lateral_agg.c.descendant_count, 0).label("child_count"),
                meta_expr.label("aggregated_metadata"),
            )
            .outerjoin(lateral_agg, literal_column("true"))
            .order_by(*order_clauses)
            .options(*self.get_eager_options())
        )

        result = await self.session.execute(final)
        rows = result.all()

        event_list: list[Event] = []
        for row in rows:
            evt = row[0]
            evt.child_count = row.child_count

            if aggregate_fields:
                merged_meta = row.aggregated_metadata
                if "_cost" in merged_meta:
                    cost_data = merged_meta.get("_cost")
                    if cost_data is None or cost_data.get("amount") is None:
                        del merged_meta["_cost"]
                    elif "currency" not in cost_data:
                        cost_data["currency"] = "usd"

                evt.user_metadata = merged_meta

            self.session.expunge(evt)
            event_list.append(evt)

        if cursor_pagination:
            has_more = 1 if len(event_list) > limit else 0
            return event_list[:limit], has_more

        total = 0
        if event_list:
            count_stmt = statement.with_only_columns(func.count()).order_by(None)
            count_result = await self.session.execute(count_stmt)
            total = count_result.scalar() or 0

        return event_list, total

    # ------------------------------------------------------------------
    # Hierarchy statistics
    # ------------------------------------------------------------------

    async def get_hierarchy_stats(
        self,
        statement: Select[tuple[Event]],
        aggregate_fields: Sequence[str] = ("cost.amount",),
        sorting: Sequence[tuple[str, bool]] = (("total", True),),
        timestamp_series: Any = None,
        interval: TimeInterval | None = None,
        timezone: str | None = None,
    ) -> Sequence[dict[str, Any]]:
        """Compute aggregate statistics grouped by root event name.

        Uses ``root_id`` for efficient rollup and joins ``event_types``
        for labels.  When ``timestamp_series`` is provided the results
        are further bucketed by time interval.

        Raises ``ValueError`` if any aggregate field fails the allowlist check
        (defense-in-depth — the API layer also validates).
        """
        _validate_aggregate_fields(aggregate_fields)
        roots_subq = (
            statement.where(
                and_(Event.parent_id.is_(None), Event.source == EventSource.user)
            )
            .order_by(None)
            .subquery()
        )

        all_evt = aliased(Event, name="all_events")
        cust = aliased(Customer, name="customer")

        time_bucket: ColumnElement[datetime] | None = None
        if (
            timestamp_series is not None
            and interval is not None
            and timezone is not None
        ):
            time_bucket = func.date_trunc(
                interval.value,
                literal_column("root_event.timestamp"),
                timezone,
            )

        # Per-root rollup columns
        rollup_cols: list[ColumnElement[Any]] = [
            literal_column("root_event.id").label("root_id"),
            literal_column("root_event.name").label("root_name"),
            literal_column("root_event.workspace_id").label("root_workspace_id"),
            cust.id.label("customer_id"),
            literal_column("root_event.external_customer_id").label(
                "external_customer_id"
            ),
        ]

        if time_bucket is not None:
            rollup_cols.append(time_bucket.label("bucket"))

        for field in aggregate_fields:
            parts = field.split(".")
            pg_path = "{" + ",".join(parts) + "}"
            safe_name = field.replace(".", "_")

            val_expr = cast(
                all_evt.user_metadata.op("#>>")(literal_column(f"'{pg_path}'")),
                Numeric,
            )
            rollup_cols.append(func.sum(val_expr).label(f"{safe_name}_total"))

        group_cols: list[ColumnElement[Any]] = [
            literal_column("root_event.id"),
            literal_column("root_event.name"),
            literal_column("root_event.workspace_id"),
            literal_column("customer.id"),
            literal_column("root_event.external_customer_id"),
        ]
        if time_bucket is not None:
            group_cols.append(time_bucket)

        rollup_query = (
            select(*rollup_cols)
            .select_from(roots_subq.alias("root_event"))
            .join(all_evt, all_evt.root_id == literal_column("root_event.id"))
            .outerjoin(
                cust,
                or_(
                    cust.id == literal_column("root_event.customer_id"),
                    and_(
                        cust.external_id
                        == literal_column("root_event.external_customer_id"),
                        cust.workspace_id == literal_column("root_event.workspace_id"),
                    ),
                ),
            )
            .group_by(*group_cols)
        )

        rollup_subq = rollup_query.subquery("per_root_totals")
        et_alias = aliased(EventType, name="event_type")

        # Build final stats query (time-bucketed or flat)
        stats = self._build_stats_query(
            rollup_subq,
            et_alias,
            aggregate_fields,
            timestamp_series,
            time_bucket,
        )

        # Sort
        sort_clauses: list[UnaryExpression[Any]] = []
        if timestamp_series is not None:
            sort_clauses.append(asc(text("timestamp")))

        for criterion, descending in sorting:
            dir_fn = desc if descending else asc
            if criterion == "name":
                sort_clauses.append(dir_fn(text("name")))
            elif criterion == "occurrences":
                sort_clauses.append(dir_fn(text("occurrences")))
            elif criterion in ("total", "average", "p10", "p90", "p99"):
                if aggregate_fields:
                    safe = aggregate_fields[0].replace(".", "_")
                    suffix_map = {
                        "total": "sum",
                        "average": "avg",
                        "p10": "p10",
                        "p90": "p90",
                        "p99": "p99",
                    }
                    sort_clauses.append(dir_fn(text(f"{safe}_{suffix_map[criterion]}")))

        if sort_clauses:
            stats = stats.order_by(*sort_clauses)

        result = await self.session.execute(stats)
        rows = result.all()

        output: list[dict[str, Any]] = []
        for row in rows:
            entry: dict[str, Any] = {
                "name": row.name,
                "label": row.label,
                "event_type_id": row.event_type_id,
                "occurrences": row.occurrences,
                "customers": row.customers,
            }

            for bucket_key in ("totals", "averages", "p10", "p90", "p99"):
                suffix = {"totals": "sum", "averages": "avg"}.get(
                    bucket_key, bucket_key
                )
                entry[bucket_key] = {
                    f.replace(".", "_"): getattr(row, f"{f.replace('.', '_')}_{suffix}")
                    or 0
                    for f in aggregate_fields
                }

            if timestamp_series is not None:
                entry["timestamp"] = row.timestamp

            output.append(entry)

        return output

    # ------------------------------------------------------------------
    # Internal: stats query builder
    # ------------------------------------------------------------------

    def _build_stats_query(
        self,
        rollup_subq: Any,
        et_alias: Any,
        aggregate_fields: Sequence[str],
        timestamp_series: Any,
        time_bucket: ColumnElement[datetime] | None,
    ) -> Any:
        """Construct the final stats SELECT depending on whether time-bucketing is used."""

        def _percentile_exprs(col: ColumnElement[Any], safe_name: str) -> list[Any]:
            filled = func.coalesce(col, 0)
            return [
                func.sum(col).label(f"{safe_name}_sum"),
                func.avg(filled).label(f"{safe_name}_avg"),
                func.percentile_cont(0.10)
                .within_group(filled)
                .label(f"{safe_name}_p10"),
                func.percentile_cont(0.90)
                .within_group(filled)
                .label(f"{safe_name}_p90"),
                func.percentile_cont(0.99)
                .within_group(filled)
                .label(f"{safe_name}_p99"),
            ]

        customer_count_expr = (
            func.count(rollup_subq.c.customer_id.distinct())
            + func.count(
                case(
                    (
                        rollup_subq.c.customer_id.is_(None),
                        rollup_subq.c.external_customer_id,
                    )
                ).distinct()
            )
        ).label("customers")

        if timestamp_series is not None:
            ts_col: ColumnElement[datetime] = timestamp_series.c.timestamp

            agg_exprs: list[Any] = []
            for field in aggregate_fields:
                safe = field.replace(".", "_")
                col = getattr(rollup_subq.c, f"{safe}_total")
                agg_exprs.extend(_percentile_exprs(col, safe))

            return (
                select(
                    ts_col.label("timestamp"),
                    rollup_subq.c.root_name.label("name"),
                    et_alias.id.label("event_type_id"),
                    et_alias.label.label("label"),
                    func.count(
                        getattr(
                            rollup_subq.c,
                            f"{aggregate_fields[0].replace('.', '_')}_total",
                        )
                    ).label("occurrences"),
                    customer_count_expr,
                    *agg_exprs,
                )
                .select_from(
                    timestamp_series.outerjoin(
                        rollup_subq,
                        rollup_subq.c.bucket == ts_col,
                    )
                )
                .outerjoin(
                    et_alias,
                    and_(
                        et_alias.name == rollup_subq.c.root_name,
                        et_alias.workspace_id == rollup_subq.c.root_workspace_id,
                    ),
                )
                .group_by(
                    ts_col,
                    rollup_subq.c.root_name,
                    et_alias.id,
                    et_alias.label,
                )
            )
        else:
            agg_exprs = []
            for field in aggregate_fields:
                safe = field.replace(".", "_")
                col_ref: ColumnElement[Any] = literal_column(f"{safe}_total")
                agg_exprs.extend(_percentile_exprs(col_ref, safe))

            return (
                select(
                    rollup_subq.c.root_name.label("name"),
                    et_alias.id.label("event_type_id"),
                    et_alias.label.label("label"),
                    func.count(rollup_subq.c.root_id).label("occurrences"),
                    customer_count_expr,
                    *agg_exprs,
                )
                .select_from(rollup_subq)
                .outerjoin(
                    et_alias,
                    and_(
                        et_alias.name == rollup_subq.c.root_name,
                        et_alias.workspace_id == rollup_subq.c.root_workspace_id,
                    ),
                )
                .group_by(rollup_subq.c.root_name, et_alias.id, et_alias.label)
            )

    # ------------------------------------------------------------------
    # Closure-table helpers
    # ------------------------------------------------------------------

    async def get_ids_and_parent_ids(
        self, event_ids: Sequence[UUID]
    ) -> Sequence[tuple[UUID, UUID | None]]:
        """Fetch ``(id, parent_id)`` pairs for the given event IDs."""
        result = await self.session.execute(
            select(Event.id, Event.parent_id).where(Event.id.in_(event_ids))
        )
        return result.all()  # type: ignore[return-value]

    async def get_ancestor_closures(
        self, descendant_id: UUID
    ) -> Sequence[tuple[UUID, int]]:
        """Return ``(ancestor_id, depth)`` rows for a single descendant."""
        result = await self.session.execute(
            select(EventClosure.ancestor_id, EventClosure.depth).where(
                EventClosure.descendant_id == descendant_id
            )
        )
        return result.all()  # type: ignore[return-value]

    async def bulk_insert_closures(
        self, closure_entries: Sequence[dict[str, Any]]
    ) -> None:
        """Insert closure-table rows."""
        if not closure_entries:
            return
        await self.session.execute(insert(EventClosure).values(closure_entries))

    async def find_parent_event(
        self, parent_id_str: str, parent_uuid: UUID | None, workspace_id: UUID
    ) -> Event | None:
        """Look up a parent event by UUID or external_id within a workspace."""
        if parent_uuid is not None:
            statement = select(Event).where(
                Event.workspace_id == workspace_id,
                or_(Event.id == parent_uuid, Event.external_id == parent_id_str),
            )
        else:
            statement = select(Event).where(
                Event.workspace_id == workspace_id,
                Event.external_id == parent_id_str,
            )
        return await self.get_one_or_none(statement)

    # ------------------------------------------------------------------
    # Ingestion validation helpers
    # ------------------------------------------------------------------

    async def get_allowed_workspace_ids(self, user_id: UUID) -> set[UUID]:
        """Return workspace IDs the user has membership in."""
        statement = select(Workspace.id).where(
            Workspace.id.in_(
                select(WorkspaceMembership.workspace_id).where(
                    WorkspaceMembership.user_id == user_id,
                    WorkspaceMembership.deleted_at.is_(None),
                )
            ),
        )
        result = await self.session.execute(statement)
        return set(result.scalars().all())

    async def get_allowed_customer_ids(
        self,
        customer_ids: set[UUID],
        auth_subject: AuthPrincipal[User | Workspace],
    ) -> set[UUID]:
        """Return the subset of *customer_ids* that are active and accessible."""
        if not customer_ids:
            return set()

        statement = select(Customer.id).where(
            Customer.deleted_at.is_(None),
            Customer.id.in_(customer_ids),
        )
        if is_user_principal(auth_subject):
            statement = statement.where(
                Customer.workspace_id.in_(
                    select(WorkspaceMembership.workspace_id).where(
                        WorkspaceMembership.user_id == auth_subject.subject.id,
                        WorkspaceMembership.deleted_at.is_(None),
                    )
                )
            )
        elif is_workspace_principal(auth_subject):
            statement = statement.where(
                Customer.workspace_id == auth_subject.subject.id
            )
        result = await self.session.execute(statement)
        return set(result.scalars().all())

    # ------------------------------------------------------------------
    # Time-series helpers
    # ------------------------------------------------------------------

    async def get_timestamp_series(self, cte: CTE) -> Sequence[datetime]:
        """Execute a timestamp-series CTE and return the timestamp column."""
        result = await self.session.execute(select(cte.c.timestamp))
        return [row[0] for row in result.all()]
