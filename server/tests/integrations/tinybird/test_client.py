"""Tests for ``rapidly/integrations/tinybird/client.py``.

The Tinybird client ships event batches to the analytics warehouse
via HTTP. Two load-bearing pins:

- **`MAX_PAYLOAD_BYTES = 10 MB`** — Tinybird's documented ingest
  limit. A regression raising the cap would silently cause Tinybird
  to reject larger batches with 413 responses (dropping events)
- **Dev-mode MockTransport** — when ``api_token`` is None, the
  httpx client uses a ``MockTransport`` returning 200. This lets
  the dev environment run without a Tinybird token while still
  exercising the ingest pipeline.
"""

from __future__ import annotations

from typing import Any

import httpx
import pytest

from rapidly.integrations.tinybird.client import (
    MAX_PAYLOAD_BYTES,
    TinybirdClient,
    TinybirdPayloadTooLargeError,
)


def _build_client(api_token: str | None = None) -> TinybirdClient:
    return TinybirdClient(
        api_url="https://api.tinybird.test",
        clickhouse_url="https://ch.tinybird.test:443",
        api_token=api_token,
        clickhouse_username="tb",
        clickhouse_token=None,
    )


class TestMaxPayloadBytes:
    def test_pinned_at_10_mib(self) -> None:
        # 10 * 1024 * 1024 = 10485760. Pin the documented limit so
        # a silent raise would be caught before Tinybird starts
        # returning 413s on production batches.
        assert MAX_PAYLOAD_BYTES == 10 * 1024 * 1024


class TestTinybirdPayloadTooLargeError:
    def test_includes_size_and_max(self) -> None:
        err = TinybirdPayloadTooLargeError(20_000_000, 10 * 1024 * 1024)
        assert err.size == 20_000_000
        assert err.max_size == 10 * 1024 * 1024
        assert "20000000" in str(err)


@pytest.mark.asyncio
class TestIngestEmptyBatch:
    async def test_empty_events_short_circuits(self) -> None:
        # Early return on empty batch — avoids a pointless HTTP
        # round-trip AND lets callers drain queues without
        # second-guessing whether the batch is worth sending.
        client = _build_client(api_token="tb_test_token")
        # Should not raise and should not touch the network.
        await client.ingest("events", events=[])


@pytest.mark.asyncio
class TestIngestPayloadSizeLimit:
    async def test_oversized_payload_raises(self) -> None:
        # A single 11 MB event should trip the limit.
        # We craft a payload whose JSON encoding will exceed the cap.
        client = _build_client(api_token="tb_test_token")
        big_value = "x" * (12 * 1024 * 1024)
        events: list[Any] = [{"id": "1", "payload": big_value}]
        with pytest.raises(TinybirdPayloadTooLargeError) as exc_info:
            await client.ingest("events", events=events)
        assert exc_info.value.size > MAX_PAYLOAD_BYTES


class TestDevModeMockTransport:
    def test_no_token_uses_mock_transport(self) -> None:
        # Dev environments without a Tinybird token: the httpx
        # client must be wired with a MockTransport so ingest
        # calls return a fake 200 instead of hitting a real endpoint
        # with a missing Authorization header.
        client = _build_client(api_token=None)
        transport = client.client._transport
        assert isinstance(transport, httpx.MockTransport)

    def test_token_present_skips_mock_transport(self) -> None:
        # Production path: real token → default httpx transport,
        # NOT the mock (regression that always-used MockTransport
        # would drop every real-environment event on the floor).
        client = _build_client(api_token="tb_prod_token")
        transport = client.client._transport
        assert not isinstance(transport, httpx.MockTransport)


class TestAuthHeader:
    def test_bearer_header_set_when_token_provided(self) -> None:
        client = _build_client(api_token="tb_test_token")
        auth = client.client.headers.get("authorization")
        assert auth == "Bearer tb_test_token"

    def test_no_auth_header_when_token_absent(self) -> None:
        # Without a token, the Authorization header is absent
        # (MockTransport doesn't need it). Pinning prevents a
        # regression that stamped a literal ``"Bearer None"`` into
        # the header — real Tinybird would 401 on that token.
        client = _build_client(api_token=None)
        assert "authorization" not in client.client.headers


class TestBaseURLAndTimeout:
    def test_base_url_set_from_api_url(self) -> None:
        client = _build_client(api_token="tb_test_token")
        assert str(client.client.base_url).startswith("https://api.tinybird.test")

    def test_timeout_is_5s_read_3s_connect(self) -> None:
        # Pin the documented timeouts — Tinybird's recommended
        # ingest timeout is ~5s; a looser cap lets slow-hanging
        # batches stall the publisher worker.
        client = _build_client(api_token="tb_test_token")
        t = client.client.timeout
        assert t.read == 5.0
        assert t.connect == 3.0


class TestExports:
    def test_all_declared(self) -> None:
        from rapidly.integrations.tinybird import client as C

        assert set(C.__all__) == {
            "TinybirdEvent",
            "TinybirdPayloadTooLargeError",
            "client",
        }
