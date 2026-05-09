"""Tests for ``rapidly/sharing/watch/types.py``.

Watch's ``source_url`` field ships a defense-in-depth validator that
rejects non-http(s) schemes (``javascript:``, ``data:``, etc.) at the
API boundary. This is the single most security-sensitive Pydantic
invariant in the chamber-types layer — pinning it prevents a silent
regression that would let a crafted session persist a URL the client
would then hand to ``<video src>``.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from rapidly.sharing.watch import types as T


class TestCreateWatchSessionRequest:
    def test_defaults(self) -> None:
        req = T.CreateWatchSessionRequest()
        assert req.title is None
        assert req.max_viewers == 10
        assert req.source_url is None
        assert req.source_kind == "url"

    def test_title_capped_at_120_chars(self) -> None:
        T.CreateWatchSessionRequest(title="a" * 120)
        with pytest.raises(ValidationError):
            T.CreateWatchSessionRequest(title="a" * 121)

    @pytest.mark.parametrize("bad", [0, -1, 11, 100])
    def test_max_viewers_rejects_out_of_range(self, bad: int) -> None:
        with pytest.raises(ValidationError):
            T.CreateWatchSessionRequest(max_viewers=bad)

    def test_source_kind_rejects_unknown(self) -> None:
        # Literal["url", "local"] — a future "webrtc" option must update
        # this enum intentionally, not by accident via client request.
        with pytest.raises(ValidationError):
            T.CreateWatchSessionRequest(source_kind="webrtc")  # type: ignore[arg-type]


class TestSourceUrlSchemeValidator:
    @pytest.mark.parametrize("ok", ["http://example.com/v.mp4", "https://a.b/c.mp4"])
    def test_accepts_http_and_https(self, ok: str) -> None:
        req = T.CreateWatchSessionRequest(source_url=ok)  # type: ignore[arg-type]
        assert req.source_url is not None
        assert str(req.source_url).startswith(("http://", "https://"))

    @pytest.mark.parametrize(
        "hostile",
        [
            "javascript:alert(1)",
            "data:text/html,<script>alert(1)</script>",
            "file:///etc/passwd",
            "ftp://example.com/a.mp4",
        ],
    )
    def test_rejects_non_http_schemes(self, hostile: str) -> None:
        # Defense-in-depth: even if Pydantic's ``AnyUrl`` accepts the
        # scheme (and it does for ``ftp``, etc.), the validator must
        # reject anything that isn't http(s). A leak here would let a
        # crafted session persist ``javascript:...`` and hand it to
        # ``<video src>`` on every subsequent guest landing.
        with pytest.raises(ValidationError):
            T.CreateWatchSessionRequest(source_url=hostile)  # type: ignore[arg-type]

    def test_none_is_accepted(self) -> None:
        # source_url is optional at creation — host can set it later.
        req = T.CreateWatchSessionRequest(source_url=None)
        assert req.source_url is None


class TestSecretGatedBodies:
    @pytest.mark.parametrize("cls", [T.MintInviteRequest, T.CloseSessionRequest])
    def test_empty_secret_is_rejected(self, cls: type) -> None:
        with pytest.raises(ValidationError):
            cls(secret="")

    @pytest.mark.parametrize("cls", [T.MintInviteRequest, T.CloseSessionRequest])
    def test_secret_over_256_is_rejected(self, cls: type) -> None:
        with pytest.raises(ValidationError):
            cls(secret="x" * 257)


class TestWatchSessionPublicView:
    def test_has_no_secret_fields(self) -> None:
        fields = set(T.WatchSessionPublicView.model_fields.keys())
        assert fields == {
            "short_slug",
            "title",
            "max_viewers",
            "source_url",
            "source_kind",
            "started_at",
            "host_connected",
        }
        assert "secret" not in fields
        assert "invite_template" not in fields
        assert "invite_token" not in fields
        assert "long_slug" not in fields
