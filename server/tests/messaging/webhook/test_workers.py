"""Tests for ``rapidly/messaging/webhook/workers.py``.

SSRF defence — ``_resolve_safe_addrs``. The webhook delivery
flow resolves the customer-supplied URL ONCE and connects to the
returned IPs directly, preventing two attack classes:

1. Direct SSRF: a customer URL pointing at 127.0.0.1, 10.0.0.5,
   169.254.169.254 (cloud metadata service), etc., would expose
   internal services. The resolver REJECTS any address in private,
   loopback, or link-local ranges.
2. DNS rebinding: a hostname that resolves to a public IP during
   validation but rebinds to a private IP at connect time. By
   returning resolved (ip, port) pairs, the caller connects to the
   IP we already vetted — the rebound private IP never enters the
   socket.

Drift in either defence would re-open SSRF.
"""

from __future__ import annotations

import socket
from typing import Any
from unittest.mock import AsyncMock

import pytest

from rapidly.messaging.webhook.workers import _resolve_safe_addrs


def _make_addrinfo_result(ip: str) -> list[Any]:
    """Build a ``getaddrinfo``-compatible result tuple for *ip*."""
    return [(socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", (ip, 0))]


def _patch_getaddrinfo(monkeypatch: pytest.MonkeyPatch, *, ips: list[str]) -> None:
    """Patch the running event loop's ``getaddrinfo`` to return the given IPs."""

    async def fake_getaddrinfo(host: str, port: int | None, **kw: Any) -> list[Any]:
        out: list[Any] = []
        for ip in ips:
            out.extend(_make_addrinfo_result(ip))
        return out

    import asyncio

    loop = asyncio.get_event_loop_policy().get_event_loop()
    monkeypatch.setattr(loop, "getaddrinfo", fake_getaddrinfo)


@pytest.mark.asyncio
class TestResolveSafeAddrs:
    async def test_public_ipv4_passes(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # Pin: a public IPv4 address resolves to (ip, default_port).
        from urllib.parse import urlparse

        # Patch the loop's getaddrinfo via a wrapper because the
        # actual test uses get_running_loop() inside the function.
        async def fake_get_running_loop_addrs(*a: Any, **kw: Any) -> list[Any]:
            return _make_addrinfo_result("8.8.8.8")

        # Replace the loop's getaddrinfo on the running event loop.
        import asyncio

        running = asyncio.get_running_loop()
        monkeypatch.setattr(
            running,
            "getaddrinfo",
            AsyncMock(return_value=_make_addrinfo_result("8.8.8.8")),
        )

        result = await _resolve_safe_addrs("https://example.com/webhook")
        assert result is not None
        assert result == [("8.8.8.8", 443)]
        # Default port for HTTPS is 443.
        _ = urlparse  # silence linter

    async def test_https_default_port_443(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import asyncio

        running = asyncio.get_running_loop()
        monkeypatch.setattr(
            running,
            "getaddrinfo",
            AsyncMock(return_value=_make_addrinfo_result("1.2.3.4")),
        )
        result = await _resolve_safe_addrs("https://example.com/hook")
        assert result == [("1.2.3.4", 443)]

    async def test_http_default_port_80(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # Pin: HTTP (not HTTPS) → port 80 default.
        import asyncio

        running = asyncio.get_running_loop()
        monkeypatch.setattr(
            running,
            "getaddrinfo",
            AsyncMock(return_value=_make_addrinfo_result("1.2.3.4")),
        )
        result = await _resolve_safe_addrs("http://example.com/hook")
        assert result == [("1.2.3.4", 80)]

    async def test_explicit_port_preserved(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Pin: ``hostname:port`` URLs preserve the explicit port
        # (some self-hosted webhook receivers run on non-standard
        # ports).
        import asyncio

        running = asyncio.get_running_loop()
        monkeypatch.setattr(
            running,
            "getaddrinfo",
            AsyncMock(return_value=_make_addrinfo_result("1.2.3.4")),
        )
        result = await _resolve_safe_addrs("https://example.com:8443/hook")
        assert result == [("1.2.3.4", 8443)]

    async def test_loopback_ipv4_rejected(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Load-bearing security pin: 127.0.0.1 / 127.0.0.0/8
        # rejected. Without it, an attacker could exfiltrate
        # internal admin endpoints by setting their webhook URL
        # to ``http://localhost/admin/...``.
        import asyncio

        running = asyncio.get_running_loop()
        monkeypatch.setattr(
            running,
            "getaddrinfo",
            AsyncMock(return_value=_make_addrinfo_result("127.0.0.1")),
        )
        result = await _resolve_safe_addrs("http://localhost/x")
        assert result is None

    async def test_private_ipv4_rejected(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # Pin: RFC 1918 private ranges (10.0.0.0/8, 172.16.0.0/12,
        # 192.168.0.0/16) — internal LAN exfil vector. Drift would
        # let an attacker probe internal services from the worker
        # via DNS that resolves to private IPs.
        import asyncio

        for ip in ("10.0.0.5", "172.16.5.5", "192.168.1.1"):
            running = asyncio.get_running_loop()
            monkeypatch.setattr(
                running,
                "getaddrinfo",
                AsyncMock(return_value=_make_addrinfo_result(ip)),
            )
            result = await _resolve_safe_addrs("https://internal.example.com/x")
            assert result is None, f"failed for {ip!r}"

    async def test_link_local_ipv4_rejected(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Pin (CRITICAL): 169.254.169.254 is the AWS / GCP / Azure
        # cloud-metadata service. An attacker who can set the
        # webhook URL could otherwise exfiltrate IAM credentials.
        # This MUST be rejected.
        import asyncio

        running = asyncio.get_running_loop()
        monkeypatch.setattr(
            running,
            "getaddrinfo",
            AsyncMock(return_value=_make_addrinfo_result("169.254.169.254")),
        )
        result = await _resolve_safe_addrs("http://attack.example.com/")
        assert result is None

    async def test_dns_rebinding_defence_returns_resolved_addrs(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Pin (security architecture): the function returns the
        # RESOLVED (ip, port) pairs (NOT the raw hostname). The
        # caller is expected to connect by IP so a hostname that
        # resolves to a public IP at validation time but rebinds
        # to private at connect time can NOT slip through.
        import asyncio

        running = asyncio.get_running_loop()
        monkeypatch.setattr(
            running,
            "getaddrinfo",
            AsyncMock(return_value=_make_addrinfo_result("8.8.8.8")),
        )
        result = await _resolve_safe_addrs("https://attacker.example.com/x")
        # The IP is in the result, NOT a hostname.
        assert result == [("8.8.8.8", 443)]

    async def test_mixed_resolution_with_one_private_rejects_entire_url(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Pin: if ANY resolved address is private, the WHOLE URL is
        # rejected (no partial allow). Otherwise an attacker could
        # craft a multi-record DNS response with one public + one
        # private IP and the worker might pick the private one.
        import asyncio

        running = asyncio.get_running_loop()
        results = _make_addrinfo_result("8.8.8.8") + _make_addrinfo_result("10.0.0.5")
        monkeypatch.setattr(running, "getaddrinfo", AsyncMock(return_value=results))
        result = await _resolve_safe_addrs("https://mixed.example.com/x")
        assert result is None

    async def test_resolution_failure_returns_none(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Defensive: gaierror / OSError during resolution → None
        # (NOT raise). The caller marks the delivery failed
        # rather than crashing the actor.
        import asyncio

        running = asyncio.get_running_loop()
        monkeypatch.setattr(
            running,
            "getaddrinfo",
            AsyncMock(side_effect=socket.gaierror("nxdomain")),
        )
        result = await _resolve_safe_addrs("https://no-such-domain.example/x")
        assert result is None

    async def test_no_hostname_returns_none(self) -> None:
        # Defensive: a malformed URL (no hostname) → None rather
        # than crashing on attribute access.
        result = await _resolve_safe_addrs("not-a-url")
        assert result is None
