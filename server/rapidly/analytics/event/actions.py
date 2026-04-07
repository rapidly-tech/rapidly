"""Event ingestion, aggregation, time-series statistics, and closure-table management."""

import uuid
from collections import defaultdict, deque
from collections.abc import Callable, Sequence
from datetime import date, datetime
from typing import Any
from zoneinfo import ZoneInfo

import logfire
import structlog
from opentelemetry import trace
from sqlalchemy import (
    Select,
    String,
    UnaryExpression,
    asc,
    cast,
    desc,
    func,
    or_,
    text,
)

from rapidly.analytics.event_type.queries import EventTypeRepository
from rapidly.core.metadata import MetadataQuery, apply_metadata_clause
from rapidly.core.ordering import Sorting
from rapidly.core.pagination import PaginationParams, paginate
from rapidly.core.queries.utils import escape_like
from rapidly.core.time_queries import TimeInterval, get_timestamp_series_cte
from rapidly.errors import (
    RapidlyError,
    RequestValidationError,
    ValidationError,
)
from rapidly.identity.auth.models import (
    AuthPrincipal,
    is_workspace_principal,
)
from rapidly.identity.member.queries import MemberRepository
from rapidly.integrations.tinybird.actions import ingest_events
from rapidly.logging import Logger
from rapidly.models import (
    Customer,
    Event,
    User,
    Workspace,
)
from rapidly.models.event import EventSource
from rapidly.platform.workspace.queries import WorkspaceRepository
from rapidly.postgres import AsyncReadSession, AsyncSession
from rapidly.worker import enqueue_events

from .ordering import EventNamesSortProperty, EventSortProperty
from .queries import EventRepository
from .types import (
    EventCreateCustomer,
    EventName,
    EventsIngest,
    EventsIngestResponse,
    EventStatistics,
    ListStatisticsTimeseries,
    StatisticsPeriod,
)

_log: Logger = structlog.get_logger(__name__)


class EventError(RapidlyError): ...


class EventIngestValidationError(EventError):
    def __init__(self, errors: list[ValidationError]) -> None:
        self.errors = errors
        super().__init__("Event ingest validation failed.")


def _topological_sort_events(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Sort events by dependency order so parents come before children.
    Events without parents come first, followed by their children in order.

    Handles parent_id references that can be either Rapidly IDs or external_id strings.
    Uses Kahn's algorithm for topological sorting.
    """
    if not events:
        return []

    id_to_index: dict[uuid.UUID | str, int] = {}
    for idx, event in enumerate(events):
        if "id" in event:
            id_to_index[event["id"]] = idx
        if "external_id" in event and event["external_id"] is not None:
            id_to_index[event["external_id"]] = idx

    graph: dict[int, list[int]] = defaultdict(list)
    in_degree: dict[int, int] = {}

    for idx in range(len(events)):
        in_degree[idx] = 0

    for idx, event in enumerate(events):
        parent_id = event.get("parent_id")
        if parent_id and parent_id in id_to_index:
            parent_idx = id_to_index[parent_id]
            graph[parent_idx].append(idx)
            in_degree[idx] += 1

    queue = deque(idx for idx in range(len(events)) if in_degree[idx] == 0)
    sorted_indices: list[int] = []

    while queue:
        current_idx = queue.popleft()
        sorted_indices.append(current_idx)

        for child_idx in graph[current_idx]:
            in_degree[child_idx] -= 1
            if in_degree[child_idx] == 0:
                queue.append(child_idx)

    if len(sorted_indices) != len(events):
        raise EventError("Circular dependency detected in event parent relationships")

    return [events[idx] for idx in sorted_indices]


# ── Query building ──


async def _build_filtered_statement(
    session: AsyncSession | AsyncReadSession,
    auth_subject: AuthPrincipal[User | Workspace],
    repository: EventRepository,
    *,
    start_timestamp: datetime | None = None,
    end_timestamp: datetime | None = None,
    workspace_id: Sequence[uuid.UUID] | None = None,
    customer_id: Sequence[uuid.UUID] | None = None,
    external_customer_id: Sequence[str] | None = None,
    name: Sequence[str] | None = None,
    source: Sequence[EventSource] | None = None,
    event_type_id: uuid.UUID | None = None,
    metadata: MetadataQuery | None = None,
    sorting: Sequence[Sorting[EventSortProperty]] = (
        (EventSortProperty.timestamp, True),
    ),
    query: str | None = None,
) -> Select[tuple[Event]]:
    statement = repository.get_readable_statement(auth_subject).options(
        *repository.get_eager_options()
    )

    if start_timestamp is not None:
        statement = statement.where(Event.timestamp > start_timestamp)

    if end_timestamp is not None:
        statement = statement.where(Event.timestamp < end_timestamp)

    if workspace_id is not None:
        statement = statement.where(Event.workspace_id.in_(workspace_id))

    if customer_id is not None:
        statement = statement.where(
            repository.get_customer_id_filter_clause(customer_id)
        )

    if external_customer_id is not None:
        statement = statement.where(
            repository.get_external_customer_id_filter_clause(external_customer_id)
        )

    if name is not None:
        statement = statement.where(Event.name.in_(name))

    if source is not None:
        statement = statement.where(Event.source.in_(source))

    if event_type_id is not None:
        statement = statement.where(Event.event_type_id == event_type_id)

    if query is not None:
        escaped = escape_like(query)
        statement = statement.where(
            or_(
                Event.name.ilike(f"%{escaped}%"),
                Event.source.ilike(f"%{escaped}%"),
                repository.get_customer_text_search_clause(escaped),
                func.to_tsvector("simple", cast(Event.user_metadata, String)).op("@@")(
                    func.plainto_tsquery(query)
                ),
            )
        )

    if metadata is not None:
        statement = apply_metadata_clause(Event, statement, metadata)

    order_by_clauses: list[UnaryExpression[Any]] = []
    for criterion, is_desc in sorting:
        clause_function = desc if is_desc else asc
        if criterion == EventSortProperty.timestamp:
            order_by_clauses.append(clause_function(Event.timestamp))
    statement = statement.order_by(*order_by_clauses)

    return statement


# ── Reads ──


async def list_events(
    session: AsyncSession | AsyncReadSession,
    auth_subject: AuthPrincipal[User | Workspace],
    *,
    start_timestamp: datetime | None = None,
    end_timestamp: datetime | None = None,
    workspace_id: Sequence[uuid.UUID] | None = None,
    customer_id: Sequence[uuid.UUID] | None = None,
    external_customer_id: Sequence[str] | None = None,
    name: Sequence[str] | None = None,
    source: Sequence[EventSource] | None = None,
    event_type_id: uuid.UUID | None = None,
    metadata: MetadataQuery | None = None,
    pagination: PaginationParams,
    sorting: Sequence[Sorting[EventSortProperty]] = (
        (EventSortProperty.timestamp, True),
    ),
    query: str | None = None,
    parent_id: uuid.UUID | None = None,
    depth: int | None = None,
    aggregate_fields: Sequence[str] = (),
    cursor_pagination: bool = False,
) -> tuple[Sequence[Event], int]:
    repository = EventRepository.from_session(session)
    statement = await _build_filtered_statement(
        session,
        auth_subject,
        repository,
        start_timestamp=start_timestamp,
        end_timestamp=end_timestamp,
        workspace_id=workspace_id,
        customer_id=customer_id,
        external_customer_id=external_customer_id,
        name=name,
        source=source,
        event_type_id=event_type_id,
        metadata=metadata,
        sorting=sorting,
        query=query,
    )

    return await repository.list_with_closure_table(
        statement,
        limit=pagination.limit,
        page=pagination.page,
        aggregate_fields=aggregate_fields,
        depth=depth,
        parent_id=parent_id,
        cursor_pagination=cursor_pagination,
        sorting=sorting,
    )


async def get(
    session: AsyncSession | AsyncReadSession,
    auth_subject: AuthPrincipal[User | Workspace],
    id: uuid.UUID,
    aggregate_fields: Sequence[str] = (),
) -> Event | None:
    repository = EventRepository.from_session(session)

    if aggregate_fields:
        return await repository.get_with_aggregation(auth_subject, id, aggregate_fields)

    statement = (
        repository.get_readable_statement(auth_subject)
        .where(Event.id == id)
        .options(*repository.get_eager_options())
    )
    return await repository.get_one_or_none(statement)


# ── Statistics ──


async def list_statistics_timeseries(
    session: AsyncSession | AsyncReadSession,
    auth_subject: AuthPrincipal[User | Workspace],
    *,
    start_date: date,
    end_date: date,
    timezone: ZoneInfo,
    interval: TimeInterval,
    workspace_id: Sequence[uuid.UUID] | None = None,
    customer_id: Sequence[uuid.UUID] | None = None,
    external_customer_id: Sequence[str] | None = None,
    name: Sequence[str] | None = None,
    source: Sequence[EventSource] | None = None,
    event_type_id: uuid.UUID | None = None,
    metadata: MetadataQuery | None = None,
    sorting: Sequence[Sorting[EventSortProperty]] = (
        (EventSortProperty.timestamp, True),
    ),
    query: str | None = None,
    aggregate_fields: Sequence[str] = ("_cost.amount",),
    hierarchy_stats_sorting: Sequence[tuple[str, bool]] = (("total", True),),
) -> ListStatisticsTimeseries:
    start_timestamp = datetime(
        start_date.year, start_date.month, start_date.day, 0, 0, 0, 0, timezone
    )
    end_timestamp = datetime(
        end_date.year, end_date.month, end_date.day, 23, 59, 59, 999999, timezone
    )

    timestamp_series_cte = get_timestamp_series_cte(
        start_timestamp, end_timestamp, interval
    )

    repository = EventRepository.from_session(session)
    statement = await _build_filtered_statement(
        session,
        auth_subject,
        repository,
        start_timestamp=start_timestamp,
        end_timestamp=end_timestamp,
        workspace_id=workspace_id,
        customer_id=customer_id,
        external_customer_id=external_customer_id,
        name=name,
        source=source,
        event_type_id=event_type_id,
        metadata=metadata,
        sorting=sorting,
        query=query,
    )

    timeseries_stats = await repository.get_hierarchy_stats(
        statement,
        aggregate_fields,
        hierarchy_stats_sorting,
        timestamp_series=timestamp_series_cte,
        interval=interval,
        timezone=str(timezone),
    )

    timestamps = await repository.get_timestamp_series(timestamp_series_cte)

    stats_by_timestamp: dict[datetime, list[dict[str, Any]]] = {}
    all_event_types: dict[tuple[str, str, uuid.UUID], dict[str, Any]] = {}

    for stat in timeseries_stats:
        ts = stat.pop("timestamp")
        if stat["name"] is None:
            continue
        if ts not in stats_by_timestamp:
            stats_by_timestamp[ts] = []
        stats_by_timestamp[ts].append(stat)

        # Track all unique event types
        event_key = (stat["name"], stat["label"], stat["event_type_id"])
        if event_key not in all_event_types:
            all_event_types[event_key] = {
                "name": stat["name"],
                "label": stat["label"],
                "event_type_id": stat["event_type_id"],
            }

    # Convert field names from dot notation to underscore (e.g., "_cost.amount" -> "_cost_amount")
    zero_values = {field.replace(".", "_"): "0" for field in aggregate_fields}

    periods = []
    for i, period_start in enumerate(timestamps):
        if i + 1 < len(timestamps):
            period_end = timestamps[i + 1]
        else:
            period_end = end_timestamp

        period_stats = stats_by_timestamp.get(period_start, [])

        # Fill in missing event types with zeros
        stats_by_name = {s["name"]: s for s in period_stats}
        complete_stats = []
        for event_type_info in all_event_types.values():
            if event_type_info["name"] in stats_by_name:
                complete_stats.append(stats_by_name[event_type_info["name"]])
            else:
                complete_stats.append(
                    {
                        **event_type_info,
                        "occurrences": 0,
                        "customers": 0,
                        "totals": zero_values,
                        "averages": zero_values,
                        "p50": zero_values,
                        "p95": zero_values,
                        "p99": zero_values,
                    }
                )

        periods.append(
            StatisticsPeriod(
                timestamp=period_start,
                period_start=period_start,
                period_end=period_end,
                stats=[EventStatistics(**s) for s in complete_stats],
            )
        )

    totals = await repository.get_hierarchy_stats(
        statement, aggregate_fields, hierarchy_stats_sorting
    )

    return ListStatisticsTimeseries(
        periods=periods,
        totals=[EventStatistics(**s) for s in totals],
    )


async def list_names(
    session: AsyncSession | AsyncReadSession,
    auth_subject: AuthPrincipal[User | Workspace],
    *,
    workspace_id: Sequence[uuid.UUID] | None = None,
    customer_id: Sequence[uuid.UUID] | None = None,
    external_customer_id: Sequence[str] | None = None,
    source: Sequence[EventSource] | None = None,
    query: str | None = None,
    pagination: PaginationParams,
    sorting: Sequence[Sorting[EventNamesSortProperty]] = [
        (EventNamesSortProperty.last_seen, True)
    ],
) -> tuple[Sequence[EventName], int]:
    repository = EventRepository.from_session(session)
    statement = repository.get_event_names_statement(auth_subject)

    if workspace_id is not None:
        statement = statement.where(Event.workspace_id.in_(workspace_id))

    if customer_id is not None:
        statement = statement.where(
            repository.get_customer_id_filter_clause(customer_id)
        )

    if external_customer_id is not None:
        statement = statement.where(
            repository.get_external_customer_id_filter_clause(external_customer_id)
        )

    if source is not None:
        statement = statement.where(Event.source.in_(source))

    if query is not None:
        statement = statement.where(Event.name.ilike(f"%{escape_like(query)}%"))

    order_by_clauses: list[UnaryExpression[Any]] = []
    for criterion, is_desc in sorting:
        clause_function = desc if is_desc else asc
        if criterion == EventNamesSortProperty.event_name:
            order_by_clauses.append(clause_function(Event.name))
        elif criterion == EventNamesSortProperty.first_seen:
            order_by_clauses.append(clause_function(text("first_seen")))
        elif criterion == EventNamesSortProperty.last_seen:
            order_by_clauses.append(clause_function(text("last_seen")))
        elif criterion == EventNamesSortProperty.occurrences:
            order_by_clauses.append(clause_function(text("occurrences")))
    statement = statement.order_by(*order_by_clauses)

    results, count = await paginate(session, statement, pagination=pagination)

    event_names: list[EventName] = []
    for result in results:
        event_name, event_source, occurrences, first_seen, last_seen = result
        event_names.append(
            EventName(
                name=event_name,
                source=event_source,
                occurrences=occurrences,
                first_seen=first_seen,
                last_seen=last_seen,
            )
        )

    return event_names, count


# ── Ingestion ──


async def ingest(
    session: AsyncSession,
    auth_subject: AuthPrincipal[User | Workspace],
    ingest: EventsIngest,
) -> EventsIngestResponse:
    validate_workspace_id = await _get_workspace_validation_function(
        session, auth_subject
    )
    customer_ids_in_batch = {
        e.customer_id for e in ingest.events if isinstance(e, EventCreateCustomer)
    }
    validate_customer_id = await _get_customer_validation_function(
        session, auth_subject, customer_ids_in_batch
    )
    member_ids_in_batch = {
        e.member_id
        for e in ingest.events
        if isinstance(e, EventCreateCustomer) and e.member_id is not None
    }
    validate_member_id = await _get_member_validation_function(
        session, member_ids_in_batch
    )

    event_type_repository = EventTypeRepository.from_session(session)
    event_types_cache: dict[tuple[str, uuid.UUID], uuid.UUID] = {}

    batch_external_id_map: dict[str, uuid.UUID] = {}
    for event_create in ingest.events:
        if event_create.external_id is not None:
            batch_external_id_map[event_create.external_id] = uuid.uuid4()

    # Build lightweight event metadata for sorting
    event_metadata: list[dict[str, Any]] = []
    for index, event_create in enumerate(ingest.events):
        metadata: dict[str, Any] = {
            "index": index,
            "external_id": event_create.external_id,
            "parent_id": event_create.parent_id,
        }
        if event_create.external_id:
            metadata["id"] = batch_external_id_map[event_create.external_id]
        event_metadata.append(metadata)

    with logfire.span("topological_sort", event_count=len(event_metadata)):
        sorted_metadata = _topological_sort_events(event_metadata)

    # Process events in sorted order
    events: list[dict[str, Any]] = []
    errors: list[ValidationError] = []
    processed_events: dict[uuid.UUID, dict[str, Any]] = {}

    with logfire.span("process_events", event_count=len(sorted_metadata)):
        for metadata in sorted_metadata:
            index = metadata["index"]
            event_create = ingest.events[index]

            try:
                workspace_id = validate_workspace_id(index, event_create.workspace_id)
                if isinstance(event_create, EventCreateCustomer):
                    validate_customer_id(index, event_create.customer_id)
                    if event_create.member_id is not None:
                        validate_member_id(index, event_create.member_id)

                parent_event: Event | None = None
                parent_id_in_batch: uuid.UUID | None = None
                if event_create.parent_id is not None:
                    parent_event, parent_id_in_batch = await _resolve_parent(
                        session,
                        index,
                        event_create.parent_id,
                        workspace_id,
                        batch_external_id_map,
                    )

                event_label_cache_key = (event_create.name, workspace_id)
                if event_label_cache_key not in event_types_cache:
                    event_type = await event_type_repository.get_or_create(
                        event_create.name, workspace_id
                    )
                    event_types_cache[event_label_cache_key] = event_type.id
                event_type_id = event_types_cache[event_label_cache_key]
            except EventIngestValidationError as e:
                errors.extend(e.errors)
                continue
            else:
                event_dict = event_create.model_dump(
                    exclude={"workspace_id", "parent_id"}, by_alias=True
                )
                event_dict["source"] = EventSource.user
                event_dict["workspace_id"] = workspace_id
                event_dict["event_type_id"] = event_type_id

                if event_create.external_id is not None:
                    event_dict["id"] = batch_external_id_map[event_create.external_id]

                if parent_event is not None:
                    event_dict["parent_id"] = parent_event.id
                    event_dict["root_id"] = parent_event.root_id or parent_event.id
                elif parent_id_in_batch is not None:
                    event_dict["parent_id"] = parent_id_in_batch
                    # Parent was already processed, look it up
                    parent_dict = processed_events.get(parent_id_in_batch)
                    if parent_dict:
                        event_dict["root_id"] = parent_dict.get(
                            "root_id", parent_id_in_batch
                        )

                events.append(event_dict)
                if event_dict.get("id"):
                    processed_events[event_dict["id"]] = event_dict

    if len(errors) > 0:
        raise RequestValidationError(errors)

    repository = EventRepository.from_session(session)
    with logfire.span("insert_batch", event_count=len(events)):
        event_ids, duplicates_count = await repository.insert_batch(events)

    with logfire.span("enqueue_events", event_count=len(event_ids)):
        enqueue_events(*event_ids)

    return EventsIngestResponse(inserted=len(event_ids), duplicates=duplicates_count)


async def create_event(session: AsyncSession, event: Event) -> Event:
    repository = EventRepository.from_session(session)
    event = await repository.create(event, flush=True)

    enqueue_events(event.id)

    _log.debug(
        "Event created",
        id=event.id,
        name=event.name,
        source=event.source,
        metadata=event.user_metadata,
    )
    return event


# ── Closure table ──


async def populate_event_closures_batch(
    session: AsyncSession, event_ids: Sequence[uuid.UUID]
) -> None:
    if not event_ids:
        return

    repository = EventRepository.from_session(session)
    events_data = await repository.get_ids_and_parent_ids(event_ids)

    events_list = [
        {"id": event_id, "parent_id": parent_id} for event_id, parent_id in events_data
    ]
    sorted_events = _topological_sort_events(events_list)

    all_closure_entries: list[dict[str, Any]] = []
    # Map event_id -> list of its ancestor closures (including self)
    event_closures: dict[uuid.UUID, list[tuple[uuid.UUID, int]]] = {}

    for event in sorted_events:
        event_id = event["id"]
        parent_id = event.get("parent_id")

        # Self-reference
        event_closures[event_id] = [(event_id, 0)]
        all_closure_entries.append(
            {
                "ancestor_id": event_id,
                "descendant_id": event_id,
                "depth": 0,
            }
        )

        if parent_id is not None:
            # Check if parent is in current batch
            if parent_id in event_closures:
                # Parent is in current batch, use in-memory closures
                for ancestor_id, depth in event_closures[parent_id]:
                    event_closures[event_id].append((ancestor_id, depth + 1))
                    all_closure_entries.append(
                        {
                            "ancestor_id": ancestor_id,
                            "descendant_id": event_id,
                            "depth": depth + 1,
                        }
                    )
            else:
                # Parent is from previous batch, query database
                parent_closures = await repository.get_ancestor_closures(parent_id)

                for ancestor_id, depth in parent_closures:
                    event_closures[event_id].append((ancestor_id, depth + 1))
                    all_closure_entries.append(
                        {
                            "ancestor_id": ancestor_id,
                            "descendant_id": event_id,
                            "depth": depth + 1,
                        }
                    )

    await repository.bulk_insert_closures(all_closure_entries)


async def ingested(session: AsyncSession, event_ids: Sequence[uuid.UUID]) -> None:
    await populate_event_closures_batch(session, event_ids)
    repository = EventRepository.from_session(session)
    statement = (
        repository.get_base_statement()
        .where(Event.id.in_(event_ids))
        .options(*repository.get_eager_options())
    )
    events = await repository.get_all(statement)
    customers: set[Customer] = set()
    workspace_ids: set[uuid.UUID] = set()
    workspace_ids_for_revops: set[uuid.UUID] = set()
    for event in events:
        workspace_ids.add(event.workspace_id)
        if event.customer:
            customers.add(event.customer)
        if "_cost" in event.user_metadata:
            workspace_ids_for_revops.add(event.workspace_id)

    span = trace.get_current_span()
    span.set_attribute("workspace_ids", [str(ws_id) for ws_id in workspace_ids])

    await ingest_events(events)

    if workspace_ids_for_revops:
        workspace_repository = WorkspaceRepository.from_session(session)
        await workspace_repository.enable_revops(workspace_ids_for_revops)


# ── Validation helpers ──


async def _get_workspace_validation_function(
    session: AsyncSession, auth_subject: AuthPrincipal[User | Workspace]
) -> Callable[[int, uuid.UUID | None], uuid.UUID]:
    if is_workspace_principal(auth_subject):

        def _validate_workspace_id_by_workspace(
            index: int, workspace_id: uuid.UUID | None
        ) -> uuid.UUID:
            if workspace_id is not None:
                raise EventIngestValidationError(
                    [
                        {
                            "type": "workspace_token",
                            "msg": (
                                "Setting workspace_id is disallowed "
                                "when using an workspace token."
                            ),
                            "loc": ("body", "events", index, "workspace_id"),
                            "input": workspace_id,
                        }
                    ]
                )
            return auth_subject.subject.id

        return _validate_workspace_id_by_workspace

    repository = EventRepository.from_session(session)
    allowed_workspaces = await repository.get_allowed_workspace_ids(
        auth_subject.subject.id
    )

    def _validate_workspace_id_by_user(
        index: int, workspace_id: uuid.UUID | None
    ) -> uuid.UUID:
        if workspace_id is None:
            raise EventIngestValidationError(
                [
                    {
                        "type": "missing",
                        "msg": "workspace_id is required.",
                        "loc": ("body", "events", index, "workspace_id"),
                        "input": None,
                    }
                ]
            )
        if workspace_id not in allowed_workspaces:
            raise EventIngestValidationError(
                [
                    {
                        "type": "workspace_id",
                        "msg": "Workspace not found.",
                        "loc": ("body", "events", index, "workspace_id"),
                        "input": workspace_id,
                    }
                ]
            )

        return workspace_id

    return _validate_workspace_id_by_user


async def _get_customer_validation_function(
    session: AsyncSession,
    auth_subject: AuthPrincipal[User | Workspace],
    customer_ids: set[uuid.UUID],
) -> Callable[[int, uuid.UUID], uuid.UUID]:
    repository = EventRepository.from_session(session)
    allowed_customers = await repository.get_allowed_customer_ids(
        customer_ids, auth_subject
    )

    def _validate_customer_id(index: int, customer_id: uuid.UUID) -> uuid.UUID:
        if customer_id not in allowed_customers:
            raise EventIngestValidationError(
                [
                    {
                        "type": "customer_id",
                        "msg": "Customer not found.",
                        "loc": ("body", "events", index, "customer_id"),
                        "input": customer_id,
                    }
                ]
            )

        return customer_id

    return _validate_customer_id


async def _get_member_validation_function(
    session: AsyncSession,
    member_ids: set[uuid.UUID],
) -> Callable[[int, uuid.UUID], uuid.UUID]:
    member_repository = MemberRepository.from_session(session)
    allowed_members = await member_repository.get_existing_ids(member_ids)

    def _validate_member_id(index: int, member_id: uuid.UUID) -> uuid.UUID:
        if member_id not in allowed_members:
            raise EventIngestValidationError(
                [
                    {
                        "type": "member_id",
                        "msg": "Member not found.",
                        "loc": ("body", "events", index, "member_id"),
                        "input": member_id,
                    }
                ]
            )

        return member_id

    return _validate_member_id


async def _resolve_parent(
    session: AsyncSession,
    index: int,
    parent_id: str,
    workspace_id: uuid.UUID,
    batch_external_id_map: dict[str, uuid.UUID],
) -> tuple[Event | None, uuid.UUID | None]:
    """
    Resolve and return the parent event.
    Returns a tuple of (parent_event_from_db, parent_id_from_batch).
    Only one of these will be set - if the parent is in the current batch,
    parent_id_from_batch will be set. Otherwise, parent_event_from_db will be set.
    """
    # Check if parent is in current batch
    if parent_id in batch_external_id_map:
        return None, batch_external_id_map[parent_id]

    # Look up parent in database by ID or external_id
    try:
        parent_uuid = uuid.UUID(parent_id)
    except ValueError:
        parent_uuid = None

    repository = EventRepository.from_session(session)
    parent_event = await repository.find_parent_event(
        parent_id, parent_uuid, workspace_id
    )

    if parent_event is not None:
        return parent_event, None

    raise EventIngestValidationError(
        [
            {
                "type": "parent_id",
                "msg": "Parent event not found.",
                "loc": ("body", "events", index, "parent_id"),
                "input": parent_id,
            }
        ]
    )
