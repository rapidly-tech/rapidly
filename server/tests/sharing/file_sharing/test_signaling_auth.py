"""Tests for the WebSocket signaling auth validator registry (PR 3).

These tests target the dispatch layer — validator registration and the thin
_AUTH_VALIDATORS lookup. Behavioural parity of the two concrete file-sharing
validators (host secret / guest reader-token / paid-channel payment-token)
is covered by existing higher-level file-sharing tests; the refactor in
this PR is a verbatim extraction with no logic change.
"""

from __future__ import annotations

from typing import Any

import pytest

from rapidly.sharing.file_sharing.signaling import (
    _AUTH_VALIDATORS,
    CANONICAL_ROLES,
    ROLE_ALIASES,
    AuthContext,
    register_auth_validator,
)


class TestRoleAliases:
    """Legacy 'uploader' / 'downloader' must normalize to canonical forms."""

    def test_uploader_aliases_to_host(self) -> None:
        assert ROLE_ALIASES["uploader"] == "host"

    def test_downloader_aliases_to_guest(self) -> None:
        assert ROLE_ALIASES["downloader"] == "guest"

    def test_canonical_roles_are_host_and_guest(self) -> None:
        assert CANONICAL_ROLES == frozenset({"host", "guest"})


class TestRegisterAuthValidator:
    """The registry must reject bad inputs at import time, not at auth time."""

    def test_rejects_non_canonical_role(self) -> None:
        """register_auth_validator must refuse 'uploader'/'downloader'.

        The legacy names are only valid on the wire; validators are always
        keyed by the canonical forms so the dispatch step is unambiguous.
        """
        with pytest.raises(RuntimeError, match="must be canonical"):

            @register_auth_validator("file", "uploader")
            async def _bad(_ctx: AuthContext) -> bool:
                return True

    def test_rejects_duplicate_registration(self) -> None:
        """Double-registering the same (kind, role) is a loud failure."""
        # Use a unique kind so we never collide with the real file validators.
        kind = "test-duplicate-kind"
        try:

            @register_auth_validator(kind, "host")
            async def _first(_ctx: AuthContext) -> bool:
                return True

            with pytest.raises(RuntimeError, match="Duplicate"):

                @register_auth_validator(kind, "host")
                async def _second(_ctx: AuthContext) -> bool:
                    return True
        finally:
            # Clean up so we don't poison other tests that share the module.
            _AUTH_VALIDATORS.pop((kind, "host"), None)

    def test_file_validators_are_registered(self) -> None:
        """Both file-sharing validators land in the registry at import time."""
        assert ("file", "host") in _AUTH_VALIDATORS
        assert ("file", "guest") in _AUTH_VALIDATORS

    def test_registered_callable_is_returned(self) -> None:
        """The decorator must return the wrapped function unchanged."""
        kind = "test-identity-kind"
        try:

            @register_auth_validator(kind, "host")
            async def my_validator(_ctx: AuthContext) -> bool:
                return True

            assert _AUTH_VALIDATORS[(kind, "host")] is my_validator
            assert my_validator.__name__ == "my_validator"
        finally:
            _AUTH_VALIDATORS.pop((kind, "host"), None)


class TestAuthContext:
    """AuthContext is a pure dataclass; confirm its shape is stable."""

    def test_fields_match_expected(self) -> None:
        from dataclasses import fields

        names = {f.name for f in fields(AuthContext)}
        assert names == {
            "ws",
            "slug",
            "role",
            "channel",
            "msg",
            "repo",
            "client_ip",
        }

    def test_role_accepts_canonical_value(self) -> None:
        # AuthContext stores the role as a str; normalization happens in
        # _authenticate before construction. We only assert the field exists
        # and accepts "host"/"guest" without error.
        ctx = AuthContext(
            ws=None,  # type: ignore[arg-type]
            slug="some-slug",
            role="host",
            channel=None,  # type: ignore[arg-type]
            msg={},
            repo=None,  # type: ignore[arg-type]
            client_ip="127.0.0.1",
        )
        assert ctx.role == "host"


class TestValidatorDispatchShape:
    """Sanity-check the lookup key shape without hitting the WebSocket."""

    def test_lookup_is_tuple_keyed(self) -> None:
        """Keys are exactly (session_kind, role). Missing pairs return None."""
        assert _AUTH_VALIDATORS.get(("file", "host")) is not None
        assert _AUTH_VALIDATORS.get(("file", "guest")) is not None
        assert _AUTH_VALIDATORS.get(("nonexistent-kind", "host")) is None
        assert _AUTH_VALIDATORS.get(("file", "admin")) is None


class TestValidatorBehaviourHost:
    """Verify _validate_file_host against FakeRedis — the extraction is
    bit-for-bit identical to the pre-refactor inline code, so this asserts
    the contract holds end-to-end for the simplest (non-paid) case.
    """

    @pytest.mark.asyncio
    async def test_valid_host_secret_passes(self, redis: Any) -> None:
        from rapidly.sharing.file_sharing.queries import ChannelRepository

        repo = ChannelRepository(redis)
        channel, raw_secret = await repo.create_channel(max_downloads=0, ttl=3600)

        validator = _AUTH_VALIDATORS[("file", "host")]
        ctx = AuthContext(
            ws=_MockWs(),  # type: ignore[arg-type]
            slug=channel.short_slug,
            role="host",
            channel=channel,
            msg={"type": "auth", "role": "host", "secret": raw_secret},
            repo=repo,
            client_ip="127.0.0.1",
        )
        assert await validator(ctx) is True

    @pytest.mark.asyncio
    async def test_wrong_host_secret_fails(self, redis: Any) -> None:
        from rapidly.sharing.file_sharing.queries import ChannelRepository

        repo = ChannelRepository(redis)
        channel, _raw_secret = await repo.create_channel(max_downloads=0, ttl=3600)

        validator = _AUTH_VALIDATORS[("file", "host")]
        ws = _MockWs()
        ctx = AuthContext(
            ws=ws,  # type: ignore[arg-type]
            slug=channel.short_slug,
            role="host",
            channel=channel,
            msg={"type": "auth", "role": "host", "secret": "wrong-secret"},
            repo=repo,
            client_ip="127.0.0.1",
        )
        assert await validator(ctx) is False
        # The validator sends a specific error + close code before returning.
        assert ws.closed is True
        assert ws.close_code == 4003


class _MockWs:
    """Minimal WebSocket stand-in for validator tests."""

    def __init__(self) -> None:
        self.sent: list[str] = []
        self.closed: bool = False
        self.close_code: int | None = None
        self.cookies: dict[str, str] = {}

    async def send_text(self, data: str) -> None:
        self.sent.append(data)

    async def close(self, code: int = 1000, reason: str = "") -> None:
        self.closed = True
        self.close_code = code
