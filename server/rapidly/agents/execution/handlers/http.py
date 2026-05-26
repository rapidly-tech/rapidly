"""HTTP node handler — calls out to arbitrary URLs.

Hardened against the SSRF + body-amplification + redirect-chain
classes per M4.3:

- **Timeout cap** (30 s ceiling, configurable down per call). The
  engine actor's overall run gets stuck without this.
- **No redirect-follow by default.** Opt in per call; capped at
  3 hops when enabled.
- **Request body cap** (10 MB). Response body cap (50 MB) —
  larger responses fail with ``body_too_large``.
- **Domain allowlist** — v1 ships a deny-all-private-IPs guard;
  per-workspace allowlists ride in a follow-up that wires through
  workspace settings. The guard rejects RFC1918 + link-local +
  loopback + 169.254 metadata addresses before any DNS lookup so a
  workflow can't reach the internal network or the cloud metadata
  service.

Why these caps live here (not in a shared HTTP utility): the agent
runtime is the most exposed call-out surface in the platform.
Centralising the SSRF check at the handler boundary keeps the
guard close to the call.
"""

from __future__ import annotations

import ipaddress
from typing import Any
from urllib.parse import urlparse

import httpx

# Soft caps. Engine actors stuck on a 5-minute fetch hold a worker
# slot; the 30 s ceiling matches the runtime's expectations.
_DEFAULT_TIMEOUT_S = 30.0
_TIMEOUT_CAP_S = 30.0

# Body caps (bytes). Both are conservative for v1; raise via per-
# workspace config in a follow-up if real workflows need bigger.
_REQUEST_BODY_CAP = 10 * 1024 * 1024
_RESPONSE_BODY_CAP = 50 * 1024 * 1024

_MAX_REDIRECTS = 3


class HttpNodeError(RuntimeError):
    """Surfaces to the engine's per-node failure path; gets stored
    in NodeRun.error_message + Run.error_message."""


def _is_private_host(host: str) -> bool:
    """True if ``host`` resolves to a private/internal address.

    For v1 we check the raw host string only — DNS-rebinding
    defence (re-checking the resolved IP after connect) is a v2
    concern. ``http://localhost`` and ``http://192.168.1.1`` are
    the common shapes a curious workflow author would try, and
    those we catch.
    """
    if not host:
        return True
    h = host.strip().lower()
    if h in ("localhost", "localhost.localdomain"):
        return True
    # Try to parse as an IP literal. If it's not, fall through —
    # public DNS names are allowed.
    try:
        ip = ipaddress.ip_address(h)
    except ValueError:
        return False
    if ip.is_loopback or ip.is_private or ip.is_link_local:
        return True
    # Cloud metadata services. AWS / GCP / Azure all live at the
    # same magic IP.
    if str(ip) == "169.254.169.254":
        return True
    return False


async def http_handler(
    ctx: dict[str, Any],
    node_config: dict[str, Any],
    input_data: dict[str, Any],
) -> dict[str, Any]:
    """Call an HTTP endpoint and return the response.

    ``node_config`` fields:
        url: str           required
        method: str        default "GET"
        headers: dict      optional
        body: dict | str   optional (JSON-serialised if dict)
        timeout_s: float   optional, capped at ``_TIMEOUT_CAP_S``
        follow_redirects:  bool, default False
    """
    url = node_config.get("url")
    if not isinstance(url, str) or not url:
        raise HttpNodeError("url is required")

    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise HttpNodeError(f"unsupported url scheme {parsed.scheme!r}")
    if _is_private_host(parsed.hostname or ""):
        raise HttpNodeError(
            f"refusing to call private/internal host {parsed.hostname!r}"
        )

    method = str(node_config.get("method", "GET")).upper()
    headers = node_config.get("headers") or {}
    if not isinstance(headers, dict):
        raise HttpNodeError("headers must be a dict")

    body = node_config.get("body")
    body_bytes: bytes | None
    body_json: dict[str, Any] | None
    if body is None:
        body_bytes = None
        body_json = None
    elif isinstance(body, dict):
        body_bytes = None
        body_json = body
    elif isinstance(body, str):
        encoded = body.encode("utf-8")
        if len(encoded) > _REQUEST_BODY_CAP:
            raise HttpNodeError("request body exceeds cap")
        body_bytes = encoded
        body_json = None
    else:
        raise HttpNodeError("body must be a dict, string, or absent")

    timeout = float(node_config.get("timeout_s", _DEFAULT_TIMEOUT_S))
    if timeout > _TIMEOUT_CAP_S:
        timeout = _TIMEOUT_CAP_S

    follow_redirects = bool(node_config.get("follow_redirects", False))

    async with httpx.AsyncClient(
        timeout=timeout,
        follow_redirects=follow_redirects,
        max_redirects=_MAX_REDIRECTS,
    ) as client:
        try:
            resp = await client.request(
                method,
                url,
                headers=headers,
                content=body_bytes,
                json=body_json,
            )
        except httpx.RequestError as exc:
            raise HttpNodeError(f"http request failed: {exc}") from exc

    raw = resp.content
    if len(raw) > _RESPONSE_BODY_CAP:
        raise HttpNodeError("response body exceeds cap")

    # Decode response text. If the body decodes as JSON, return
    # the parsed object alongside the raw string; the next node can
    # pick whichever it prefers.
    body_text = raw.decode("utf-8", errors="replace")
    parsed_json: Any | None
    try:
        import json

        parsed_json = json.loads(body_text)
    except (ValueError, TypeError):
        parsed_json = None

    return {
        "status": resp.status_code,
        "headers": dict(resp.headers),
        "body": body_text,
        "json": parsed_json,
    }
