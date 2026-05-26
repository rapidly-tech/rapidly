"""Tests for the HTTP node handler.

The SSRF guard is the most security-critical bit — covered with
parametrised cases over the private-IP / localhost / metadata
shapes. The happy-path call uses an httpx mock transport so the
test doesn't actually hit the network.
"""

from __future__ import annotations

import json

import httpx
import pytest

from rapidly.agents.execution.handlers.http import (
    HttpNodeError,
    _is_private_host,
    http_handler,
)


class TestPrivateHostGuard:
    @pytest.mark.parametrize(
        "host",
        [
            "localhost",
            "127.0.0.1",
            "127.1.2.3",
            "10.0.0.1",
            "172.16.0.1",
            "192.168.1.1",
            "169.254.169.254",  # cloud metadata
            "169.254.0.1",  # link-local
            "::1",
            "fc00::1",  # IPv6 ULA
            "",  # empty
        ],
    )
    def test_rejects(self, host: str) -> None:
        assert _is_private_host(host) is True

    @pytest.mark.parametrize(
        "host",
        [
            "example.com",
            "api.openai.com",
            "8.8.8.8",
            "1.1.1.1",
        ],
    )
    def test_allows(self, host: str) -> None:
        assert _is_private_host(host) is False


@pytest.mark.asyncio
class TestHandlerValidation:
    async def test_rejects_missing_url(self) -> None:
        with pytest.raises(HttpNodeError, match="url is required"):
            await http_handler({}, {}, {})

    async def test_rejects_unsupported_scheme(self) -> None:
        with pytest.raises(HttpNodeError, match="unsupported url scheme"):
            await http_handler({}, {"url": "file:///etc/passwd"}, {})

    async def test_rejects_private_host(self) -> None:
        with pytest.raises(HttpNodeError, match="private/internal host"):
            await http_handler({}, {"url": "http://localhost/whatever"}, {})

    async def test_rejects_cloud_metadata_url(self) -> None:
        with pytest.raises(HttpNodeError, match="private/internal host"):
            await http_handler(
                {}, {"url": "http://169.254.169.254/latest/meta-data/"}, {}
            )


@pytest.mark.asyncio
class TestHandlerHappyPath:
    async def _patched_client(
        self, monkeypatch: pytest.MonkeyPatch, response: httpx.Response
    ) -> None:
        """Swap httpx.AsyncClient for one with a MockTransport."""

        def handler(_request: httpx.Request) -> httpx.Response:
            return response

        original_init = httpx.AsyncClient.__init__

        def patched_init(
            self: httpx.AsyncClient, *args: object, **kwargs: object
        ) -> None:
            kwargs["transport"] = httpx.MockTransport(handler)
            original_init(self, *args, **kwargs)

        monkeypatch.setattr(httpx.AsyncClient, "__init__", patched_init)

    async def test_get_returns_status_headers_body(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        await self._patched_client(
            monkeypatch,
            httpx.Response(
                200,
                headers={"content-type": "application/json"},
                content=b'{"hello":"world"}',
            ),
        )
        result = await http_handler(
            {}, {"url": "https://example.com/ping", "method": "GET"}, {}
        )
        assert result["status"] == 200
        assert result["body"] == '{"hello":"world"}'
        assert result["json"] == {"hello": "world"}

    async def test_non_json_response_returns_null_json_field(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        await self._patched_client(
            monkeypatch,
            httpx.Response(200, content=b"plain text body"),
        )
        result = await http_handler({}, {"url": "https://example.com/text"}, {})
        assert result["json"] is None
        assert result["body"] == "plain text body"

    async def test_dict_body_serialised_as_json(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        seen: list[bytes] = []

        def handler(request: httpx.Request) -> httpx.Response:
            seen.append(request.content)
            return httpx.Response(200, content=b"ok")

        original_init = httpx.AsyncClient.__init__

        def patched_init(
            self: httpx.AsyncClient, *args: object, **kwargs: object
        ) -> None:
            kwargs["transport"] = httpx.MockTransport(handler)
            original_init(self, *args, **kwargs)

        monkeypatch.setattr(httpx.AsyncClient, "__init__", patched_init)

        await http_handler(
            {},
            {
                "url": "https://example.com/post",
                "method": "POST",
                "body": {"x": 1, "y": "z"},
            },
            {},
        )
        assert json.loads(seen[0]) == {"x": 1, "y": "z"}
