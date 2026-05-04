"""Tests for ``rapidly/analytics/event/types.py``.

Event types carry several load-bearing invariants that the module's
docstring advertises but no test exercised:

- ``is_past_timestamp`` — rejects future timestamps so ingestion cannot
  poison statistics with arbitrary forward-dated events
- ``metadata`` carries ``serialization_alias="user_metadata"`` — a
  rename of either the attribute or the alias would break wire
  compatibility with the dashboard + customer SDK
- ``Event`` is a discriminated union on ``source`` (system / user),
  and ``SystemEvent`` discriminates on ``name`` — a caller who sends
  ``source=system`` must select a valid system-event ``name``
- ``CostMetadata.currency`` has a ``usd``-only pattern — regression
  accepting other currencies would silently mis-aggregate statistics
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from pydantic import TypeAdapter, ValidationError

from rapidly.analytics.event.types import (
    CostMetadata,
    EventCreateCustomer,
    EventCreateExternalCustomer,
    EventsIngest,
    EventsIngestResponse,
    EventTypeAdapter,
    SystemEvent,
    is_past_timestamp,
    metadata_default_factory,
)


class TestIsPastTimestamp:
    def test_accepts_past_timestamp(self) -> None:
        ts = datetime.now(UTC) - timedelta(minutes=1)
        assert is_past_timestamp(ts) == ts

    def test_accepts_naive_in_past_after_coercion(self) -> None:
        # The helper ``astimezone``s the input to UTC. Passing a
        # tz-aware value a minute in the past must pass.
        ts = datetime.now(UTC) - timedelta(seconds=5)
        assert is_past_timestamp(ts) == ts

    def test_rejects_future_timestamp(self) -> None:
        # Event ingestion must not accept future timestamps —
        # forward-dated events would poison time-series stats (a
        # spike "in the future" that disappears once now catches up).
        ts = datetime.now(UTC) + timedelta(minutes=5)
        with pytest.raises(ValueError, match="past"):
            is_past_timestamp(ts)


class TestEventCreateCustomerPath:
    def test_accepts_customer_id(self) -> None:
        body = EventCreateCustomer(
            name="checkout.completed",
            customer_id=uuid4(),
        )
        assert body.name == "checkout.completed"

    def test_rejects_future_timestamp_via_afterwalidator(self) -> None:
        with pytest.raises(ValidationError):
            EventCreateCustomer(
                name="x",
                customer_id=uuid4(),
                timestamp=datetime.now(UTC) + timedelta(hours=1),
            )

    def test_default_timestamp_is_aware(self) -> None:
        # Pydantic's ``AwareDatetime`` requires tz. Pinning the
        # default-factory result is tz-aware prevents a regression
        # that swaps in ``datetime.now()`` (naive) and breaks every
        # caller who omits the timestamp.
        body = EventCreateCustomer(name="x", customer_id=uuid4())
        assert body.timestamp.tzinfo is not None

    def test_metadata_default_is_empty_dict(self) -> None:
        body = EventCreateCustomer(name="x", customer_id=uuid4())
        assert body.metadata == {}
        assert metadata_default_factory() == {}


class TestEventCreateExternalCustomerPath:
    def test_accepts_external_customer_id(self) -> None:
        body = EventCreateExternalCustomer(
            name="checkout.completed",
            external_customer_id="cust_123",
        )
        assert body.external_customer_id == "cust_123"

    def test_customer_path_and_external_path_are_distinct(self) -> None:
        # The union ``EventCreate = EventCreateCustomer |
        # EventCreateExternalCustomer`` means a body without either id
        # field must fail on BOTH branches — pinning the union rejects
        # an empty payload.
        Adapter: TypeAdapter[EventCreateCustomer | EventCreateExternalCustomer] = (
            TypeAdapter(EventCreateCustomer | EventCreateExternalCustomer)
        )
        with pytest.raises(ValidationError):
            Adapter.validate_python({"name": "x"})


class TestEventsIngestResponse:
    def test_duplicates_defaults_to_zero(self) -> None:
        # Pinning the default keeps backward compat with older SDKs
        # that don't know to read ``duplicates`` from the response.
        resp = EventsIngestResponse(inserted=3)
        assert resp.duplicates == 0

    def test_ingest_envelope_requires_events_list(self) -> None:
        with pytest.raises(ValidationError):
            EventsIngest.model_validate({})


class TestCostMetadataCurrencyPattern:
    def test_accepts_usd(self) -> None:
        from pydantic import TypeAdapter

        ta: TypeAdapter[CostMetadata] = TypeAdapter(CostMetadata)
        ta.validate_python({"amount": "1.23", "currency": "usd"})

    def test_rejects_non_usd_currency(self) -> None:
        # ``CostMetadata.currency`` is pattern-constrained to ``usd``.
        # A regression accepting EUR / GBP would silently mis-aggregate
        # cost statistics (summing cents across mixed currencies).
        from pydantic import TypeAdapter

        ta: TypeAdapter[CostMetadata] = TypeAdapter(CostMetadata)
        with pytest.raises(ValidationError):
            ta.validate_python({"amount": "1.00", "currency": "eur"})


class TestSerializationAlias:
    def test_metadata_serializes_as_user_metadata(self) -> None:
        # Wire-format pin: the dashboard + customer SDK read
        # ``user_metadata`` on the response — a rename to the Python
        # attribute ``metadata`` would break both. The alias makes
        # the serialised key differ from the attribute name.
        body = EventCreateCustomer(
            name="x",
            customer_id=uuid4(),
            metadata={"key": "value"},  # type: ignore[typeddict-unknown-key]
        )
        dumped = body.model_dump(by_alias=True)
        assert "user_metadata" in dumped
        assert dumped["user_metadata"] == {"key": "value"}


class TestDiscriminatedUnions:
    # ``Event`` dispatches on ``source`` (system / user). ``SystemEvent``
    # then dispatches on ``name``. Pinning the discriminator behaviour
    # catches a regression that collapses the discriminated union back
    # to a plain union (slower + looser).

    def test_unknown_source_is_rejected(self) -> None:
        with pytest.raises(ValidationError):
            EventTypeAdapter.validate_python(
                {
                    "id": str(uuid4()),
                    "source": "not_a_known_source",
                    "name": "x",
                    "timestamp": datetime.now(UTC).isoformat(),
                    "workspace_id": str(uuid4()),
                    "customer_id": None,
                    "customer": None,
                    "external_customer_id": None,
                    "label": "x",
                    "metadata": {},
                }
            )

    def test_system_event_requires_known_name(self) -> None:
        # SystemEvent is discriminated on ``name`` — only the three
        # known SystemEventEnum values dispatch. A caller sending
        # ``source=system`` + ``name=garbage`` must fail.
        Adapter: TypeAdapter[SystemEvent] = TypeAdapter(SystemEvent)
        with pytest.raises(ValidationError):
            Adapter.validate_python(
                {
                    "id": str(uuid4()),
                    "source": "system",
                    "name": "garbage.unknown",
                    "timestamp": datetime.now(UTC).isoformat(),
                    "workspace_id": str(uuid4()),
                    "customer_id": None,
                    "customer": None,
                    "external_customer_id": None,
                    "label": "x",
                    "metadata": {},
                }
            )
