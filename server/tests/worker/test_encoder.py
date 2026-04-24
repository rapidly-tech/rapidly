"""Tests for ``rapidly/worker/_encoder.py``.

The Dramatiq JSONEncoder strips middleware-injected ephemeral keys
from the message options before serialisation. Keeping those keys
out of the on-wire payload matters for two reasons:

1. **Redis footprint** — some middleware options (debounce state,
   internal traces) can add hundreds of bytes per message. Over
   millions of messages this compounds into GBs of Redis memory
2. **Security** — ephemeral keys sometimes carry sensitive
   per-request context (auth subject, tracing baggage); they
   should never be persisted into the queue
"""

from __future__ import annotations

import json
import uuid
from typing import Any
from unittest.mock import MagicMock

import pytest

from rapidly.worker._encoder import JSONEncoder, _default_serializer


class TestDefaultSerializer:
    def test_uuid_serialises_to_str(self) -> None:
        u = uuid.uuid4()
        assert _default_serializer(u) == str(u)

    def test_unknown_type_raises(self) -> None:
        # Explicit opt-in — no accidental serialisation of arbitrary
        # Python objects that might leak state into queued messages.
        with pytest.raises(TypeError, match="Cannot serialise"):
            _default_serializer(object())


class TestJSONEncoderWithoutBroker:
    def test_no_broker_means_no_stripping(self) -> None:
        encoder = JSONEncoder(broker=None)
        payload: dict[str, Any] = {
            "options": {"foo": 1, "bar": 2},
            "queue_name": "default",
        }
        encoded = encoder.encode(payload)
        assert json.loads(encoded) == payload

    def test_uuid_in_payload_is_stringified(self) -> None:
        encoder = JSONEncoder(broker=None)
        mid = uuid.uuid4()
        encoded = encoder.encode({"message_id": mid})
        data = json.loads(encoded)
        assert data["message_id"] == str(mid)

    def test_encoder_output_is_utf8_bytes(self) -> None:
        encoder = JSONEncoder(broker=None)
        encoded = encoder.encode({"message": "héllo"})
        assert isinstance(encoded, bytes)
        # Non-ASCII escapes to \\uXXXX (default json.dumps behaviour)
        # but still round-trips to the original on decode+json.loads.
        decoded = encoded.decode("utf-8")
        assert json.loads(decoded)["message"] == "héllo"

    def test_compact_separators(self) -> None:
        # Compact JSON (``,`` / ``:`` with no spaces) shaves bytes
        # off every queued message — at scale this saves
        # meaningful Redis bandwidth + memory.
        encoder = JSONEncoder(broker=None)
        encoded = encoder.encode({"a": 1, "b": 2})
        assert b", " not in encoded
        assert b": " not in encoded


class TestJSONEncoderWithBroker:
    def test_collects_ephemeral_keys_from_all_middleware(self) -> None:
        mw1 = MagicMock()
        mw1.ephemeral_options = {"debounce_key", "trace_id"}
        mw2 = MagicMock()
        mw2.ephemeral_options = {"auth_subject"}
        broker = MagicMock()
        broker.middleware = [mw1, mw2]

        encoder = JSONEncoder(broker=broker)
        assert encoder._ephemeral_keys == {
            "debounce_key",
            "trace_id",
            "auth_subject",
        }

    def test_strips_only_ephemeral_keys_from_options(self) -> None:
        # Load-bearing pin: non-ephemeral options (eg ``queue_name``
        # timestamps) must survive; only the registered ephemeral
        # keys are scrubbed.
        mw = MagicMock()
        mw.ephemeral_options = {"debounce_key"}
        broker = MagicMock()
        broker.middleware = [mw]

        encoder = JSONEncoder(broker=broker)
        encoded = encoder.encode(
            {
                "message_id": "m1",
                "options": {
                    "debounce_key": "secret_auth_token",
                    "max_retries": 3,
                },
            }
        )
        data = json.loads(encoded)
        # The ephemeral key is GONE from the persisted payload.
        assert "debounce_key" not in data["options"]
        # Non-ephemeral options survive.
        assert data["options"]["max_retries"] == 3
        # Outer keys untouched.
        assert data["message_id"] == "m1"

    def test_no_options_key_means_no_stripping(self) -> None:
        # If the message has no ``options`` key at all, the stripper
        # must not fail — some raw Dramatiq messages don't carry
        # options.
        mw = MagicMock()
        mw.ephemeral_options = {"debounce_key"}
        broker = MagicMock()
        broker.middleware = [mw]

        encoder = JSONEncoder(broker=broker)
        encoded = encoder.encode({"message_id": "m1"})
        data = json.loads(encoded)
        assert data == {"message_id": "m1"}

    def test_middleware_without_ephemeral_options_attr(self) -> None:
        # ``getattr(mw, "ephemeral_options", set())`` — middleware
        # classes that don't declare the attribute must not crash
        # encoder construction.
        mw_without = MagicMock(spec=[])  # no attributes
        broker = MagicMock()
        broker.middleware = [mw_without]

        encoder = JSONEncoder(broker=broker)
        assert encoder._ephemeral_keys == frozenset()

    def test_empty_ephemeral_keys_leaves_options_untouched(self) -> None:
        # If no middleware advertises ephemeral options, the options
        # dict should round-trip unchanged.
        broker = MagicMock()
        broker.middleware = []

        encoder = JSONEncoder(broker=broker)
        encoded = encoder.encode({"options": {"max_retries": 3, "priority": "high"}})
        data = json.loads(encoded)
        assert data["options"] == {"max_retries": 3, "priority": "high"}
