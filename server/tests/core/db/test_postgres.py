"""Tests for ``rapidly/core/db/postgres.py``.

Async + sync engine / sessionmaker factories. Three load-bearing
surfaces:

- ``json_serializer`` (used by SQLAlchemy for JSONB columns) handles
  ``Decimal`` by converting to ``float``. Drift would crash on
  every JSONB row that carries a Decimal value (Stripe amounts,
  customer balances, etc.) and the request would 500.
- ``_async_connect_args`` and ``_sync_connect_args`` build driver-
  specific ``connect_args`` dicts:
  * asyncpg uses ``server_settings={"application_name": ...}`` and
    a top-level ``command_timeout`` field
  * psycopg2 uses ``application_name`` directly and encodes
    statement_timeout via the ``options`` string in MILLISECONDS
  Drift would silently fall back to the driver's defaults and lose
  per-process attribution in ``pg_stat_activity`` + the timeout
  guard.
- ``create_async_sessionmaker`` sets ``expire_on_commit=False``
  so attributes remain accessible after commit (FastAPI returns
  serialised models AFTER the session commits). Drift to True
  would crash every endpoint that touches a returned ORM object
  post-commit.
"""

from __future__ import annotations

import json
from decimal import Decimal

import pytest

from rapidly.core.db.postgres import (
    _async_connect_args,
    _decimal_aware_default,
    _sync_connect_args,
    json_serializer,
)


class TestDecimalAwareDefault:
    def test_decimal_converts_to_float(self) -> None:
        # Pin: Decimal → float. Drift would crash JSON encoding
        # on every JSONB column with a financial amount.
        assert _decimal_aware_default(Decimal("1.50")) == 1.5

    def test_unknown_type_raises_type_error(self) -> None:
        # Pin: unknown types raise TypeError loudly. Defends
        # against silent passthrough of non-JSON-encodable values.
        class _Custom:
            pass

        with pytest.raises(TypeError, match="Cannot JSON-encode"):
            _decimal_aware_default(_Custom())


class TestJsonSerializer:
    def test_decimal_round_trips_via_float(self) -> None:
        # Pin end-to-end: a payload carrying Decimal serialises
        # to a JSON number.
        payload = {"amount": Decimal("19.99")}
        result = json_serializer(payload)
        # Decoded JSON gives float (NOT scientific notation).
        assert json.loads(result) == {"amount": 19.99}

    def test_plain_payload_serialises(self) -> None:
        result = json_serializer({"a": 1, "b": "x"})
        assert json.loads(result) == {"a": 1, "b": "x"}


class TestAsyncConnectArgs:
    def test_application_name_in_server_settings(self) -> None:
        # Pin: asyncpg expects ``server_settings`` for app name
        # (NOT a top-level ``application_name``). Drift would
        # silently lose per-process attribution.
        args = _async_connect_args("api.worker", None)
        assert args == {"server_settings": {"application_name": "api.worker"}}

    def test_command_timeout_top_level(self) -> None:
        # Pin: ``command_timeout`` is a top-level asyncpg arg
        # (NOT under server_settings).
        args = _async_connect_args(None, 30.0)
        assert args == {"command_timeout": 30.0}

    def test_both_set_combines(self) -> None:
        args = _async_connect_args("svc", 5.0)
        assert args == {
            "server_settings": {"application_name": "svc"},
            "command_timeout": 5.0,
        }

    def test_neither_set_returns_empty(self) -> None:
        # Pin: omitting both yields empty dict — driver uses its
        # own defaults.
        assert _async_connect_args(None, None) == {}


class TestSyncConnectArgs:
    def test_application_name_top_level(self) -> None:
        # Pin: psycopg2 uses ``application_name`` directly (NOT
        # ``server_settings``). Drift to asyncpg-shaped args
        # would silently fail to set the attribution.
        args = _sync_connect_args("api.web", None)
        assert args == {"application_name": "api.web"}

    def test_command_timeout_encoded_as_options_milliseconds(self) -> None:
        # Pin: psycopg2 has no native command_timeout; we encode
        # statement_timeout in MILLISECONDS via the ``options``
        # connection string. Drift to seconds would set a
        # 1000x-too-short timeout and break every long query.
        args = _sync_connect_args(None, 30.0)
        assert args == {"options": "-c statement_timeout=30000"}

    def test_command_timeout_uses_int_milliseconds(self) -> None:
        # Pin: float seconds → int ms. A regression that emitted
        # the float ms (e.g. ``30000.5``) would be rejected by
        # Postgres as a malformed connection option.
        args = _sync_connect_args(None, 0.5)
        assert args["options"] == "-c statement_timeout=500"

    def test_both_set_combines(self) -> None:
        args = _sync_connect_args("svc", 1.0)
        assert args == {
            "application_name": "svc",
            "options": "-c statement_timeout=1000",
        }

    def test_neither_set_returns_empty(self) -> None:
        assert _sync_connect_args(None, None) == {}


class TestExports:
    def test_dunder_all_pinned(self) -> None:
        # Pin: the public exports. Callers import these names
        # directly.
        from rapidly.core.db import postgres as M

        assert "create_async_engine" in M.__all__
        assert "create_async_sessionmaker" in M.__all__
        assert "AsyncSession" in M.__all__
        assert "AsyncReadSession" in M.__all__
        assert "AsyncSessionMaker" in M.__all__
        assert "AsyncReadSessionMaker" in M.__all__
