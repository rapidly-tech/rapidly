"""Tests for ``rapidly/customers/customer/workers.py``.

Customer-lifecycle background actors. Three load-bearing surfaces:

- Exception hierarchy: ``CustomerDoesNotExist`` extends
  ``CustomerTaskError`` extends ``BackgroundTaskError`` so the
  worker retry middleware classifies it correctly.
  ``CustomerDoesNotExist`` exposes ``customer_id`` for incident
  triage.
- ``customer_webhook`` actor raises ``CustomerDoesNotExist`` when
  the customer isn't found (defensive against a webhook task
  fired before the customer transaction commits) AND uses
  ``include_deleted=True`` so soft-deleted customers can still
  emit their final ``customer.deleted`` webhook.
- ``customer_event`` builds ``SystemEvent`` payloads with the
  documented metadata key set: ``customer_id``,
  ``customer_email``, ``customer_name``, ``customer_external_id``
  for created/deleted; PLUS ``updated_fields`` for updated
  events. Drift in any key would silently break analytics
  ingestion. ``updated_fields=None`` falls back to ``{}`` (not
  None) so the SystemEvent JSON schema validates.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from rapidly.analytics.event.system import SystemEvent
from rapidly.customers.customer import workers as M
from rapidly.customers.customer.workers import (
    CustomerDoesNotExist,
    CustomerTaskError,
    customer_event,
    customer_webhook,
)
from rapidly.errors import BackgroundTaskError


class TestExceptionHierarchy:
    def test_customer_task_error_extends_background_task_error(self) -> None:
        assert issubclass(CustomerTaskError, BackgroundTaskError)

    def test_customer_does_not_exist_extends_customer_task_error(self) -> None:
        assert issubclass(CustomerDoesNotExist, CustomerTaskError)


class TestCustomerDoesNotExist:
    def test_carries_customer_id(self) -> None:
        cid = uuid4()
        err = CustomerDoesNotExist(cid)
        assert err.customer_id == cid

    def test_message_includes_customer_id(self) -> None:
        cid = uuid4()
        err = CustomerDoesNotExist(cid)
        assert str(cid) in str(err)


def _customer(**overrides: Any) -> Any:
    """Build a Customer-spec'd mock with the attrs the workers read."""
    c = MagicMock()
    c.id = overrides.get("id", uuid4())
    c.email = overrides.get("email", "alice@example.com")
    c.name = overrides.get("name", "Alice")
    c.external_id = overrides.get("external_id", "ext-1")
    c.workspace = overrides.get("workspace", MagicMock())
    return c


def _patch_async_session(
    monkeypatch: pytest.MonkeyPatch, *, customer: Any | None
) -> Any:
    """Replace AsyncSessionMaker + CustomerRepository for the actor body."""
    cm = AsyncMock()
    cm.__aenter__ = AsyncMock(return_value=MagicMock())
    cm.__aexit__ = AsyncMock(return_value=False)
    monkeypatch.setattr(M, "AsyncSessionMaker", lambda: cm)

    repo = MagicMock()
    repo.get_by_id = AsyncMock(return_value=customer)
    repo_cls = MagicMock()
    repo_cls.from_session = MagicMock(return_value=repo)
    monkeypatch.setattr(M, "CustomerRepository", repo_cls)
    return repo


@pytest.mark.asyncio
class TestCustomerWebhookActor:
    async def test_raises_when_customer_missing(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Pin: missing customer → CustomerDoesNotExist (NOT silent
        # no-op). The retry budget surfaces the failure, and the
        # dead-letter queue captures the customer_id for triage.
        _patch_async_session(monkeypatch, customer=None)
        cid = uuid4()
        with pytest.raises(CustomerDoesNotExist) as exc:
            await customer_webhook.__wrapped__(  # type: ignore[attr-defined]
                event_type=MagicMock(), customer_id=cid
            )
        assert exc.value.customer_id == cid

    async def test_uses_include_deleted_so_deleted_customers_can_emit_final_webhook(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Pin (load-bearing): the lookup MUST use include_deleted=True
        # so a soft-deleted customer's final ``customer.deleted``
        # webhook still fires. Drift to default include_deleted=False
        # would silently lose every deletion notification.
        repo = _patch_async_session(monkeypatch, customer=_customer())

        async def fake_webhook(
            session: Any, redis: Any, event_type: Any, customer: Any
        ) -> None:
            return None

        fake_actions = MagicMock()
        fake_actions.webhook = fake_webhook
        monkeypatch.setattr(M, "customer_service", fake_actions)
        monkeypatch.setattr(
            "rapidly.customers.customer.workers.RedisMiddleware.get",
            staticmethod(lambda: AsyncMock()),
        )

        await customer_webhook.__wrapped__(  # type: ignore[attr-defined]
            event_type=MagicMock(), customer_id=uuid4()
        )

        # Verify include_deleted=True was passed.
        call = repo.get_by_id.call_args
        assert call.kwargs["include_deleted"] is True


@pytest.mark.asyncio
class TestCustomerEventActor:
    async def _setup_event_capture(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> dict[str, Any]:
        captured: dict[str, Any] = {}

        async def fake_create_event(session: Any, event: Any) -> None:
            captured["event"] = event

        # Patch the event-service module reference inside the worker.
        monkeypatch.setattr(
            "rapidly.customers.customer.workers.event_service.create_event",
            fake_create_event,
        )

        # Patch build_system_event to return its kwargs untouched
        # so we can assert on metadata directly.
        def fake_build(name: Any, **kwargs: Any) -> Any:
            payload = MagicMock()
            payload.name = name
            payload.kwargs = kwargs
            return payload

        monkeypatch.setattr(
            "rapidly.customers.customer.workers.build_system_event", fake_build
        )
        return captured

    async def test_raises_when_customer_missing(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _patch_async_session(monkeypatch, customer=None)
        await self._setup_event_capture(monkeypatch)
        with pytest.raises(CustomerDoesNotExist):
            await customer_event.__wrapped__(  # type: ignore[attr-defined]
                customer_id=uuid4(),
                event_name=SystemEvent.customer_created,
            )

    async def test_created_event_metadata_keys(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Pin the metadata schema for customer.created. Drift in
        # any key would silently break analytics ingestion.
        cust = _customer()
        _patch_async_session(monkeypatch, customer=cust)
        captured = await self._setup_event_capture(monkeypatch)

        await customer_event.__wrapped__(  # type: ignore[attr-defined]
            customer_id=cust.id,
            event_name=SystemEvent.customer_created,
        )

        event = captured["event"]
        assert event.name == SystemEvent.customer_created
        meta = event.kwargs["metadata"]
        assert set(meta.keys()) == {
            "customer_id",
            "customer_email",
            "customer_name",
            "customer_external_id",
        }
        assert meta["customer_id"] == str(cust.id)
        assert meta["customer_email"] == cust.email

    async def test_deleted_event_metadata_keys(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Pin: deleted carries the SAME 4 keys as created (no
        # updated_fields).
        cust = _customer()
        _patch_async_session(monkeypatch, customer=cust)
        captured = await self._setup_event_capture(monkeypatch)

        await customer_event.__wrapped__(  # type: ignore[attr-defined]
            customer_id=cust.id,
            event_name=SystemEvent.customer_deleted,
        )

        event = captured["event"]
        meta = event.kwargs["metadata"]
        assert set(meta.keys()) == {
            "customer_id",
            "customer_email",
            "customer_name",
            "customer_external_id",
        }

    async def test_updated_event_includes_updated_fields(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Pin: customer.updated carries the 4 base keys PLUS
        # ``updated_fields``. Drift would lose the diff that
        # downstream consumers (notification policies,
        # CRM sync) read.
        cust = _customer()
        _patch_async_session(monkeypatch, customer=cust)
        captured = await self._setup_event_capture(monkeypatch)

        updated_fields = {"email": True, "name": True}
        await customer_event.__wrapped__(  # type: ignore[attr-defined]
            customer_id=cust.id,
            event_name=SystemEvent.customer_updated,
            updated_fields=updated_fields,
        )

        meta = captured["event"].kwargs["metadata"]
        assert meta["updated_fields"] == updated_fields

    async def test_updated_event_falls_back_to_empty_dict_when_none(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Pin: ``updated_fields=None`` falls back to ``{}`` (not
        # None) so the SystemEvent JSON schema validates. Drift
        # to None would break the analytics pipeline.
        cust = _customer()
        _patch_async_session(monkeypatch, customer=cust)
        captured = await self._setup_event_capture(monkeypatch)

        await customer_event.__wrapped__(  # type: ignore[attr-defined]
            customer_id=cust.id,
            event_name=SystemEvent.customer_updated,
            updated_fields=None,
        )

        meta = captured["event"].kwargs["metadata"]
        assert meta["updated_fields"] == {}
