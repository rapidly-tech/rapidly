"""Tests for ``rapidly/sharing/screen/types.py``.

Pins the Pydantic invariants on the Screen chamber API surface:
- ``max_viewers`` bounded at 1..10 (host-upload bandwidth ceiling)
- ``secret`` bounded at 1..256 (refuses empty-string host auth)
- ``title`` capped at 120 chars
- ``ScreenSessionPublicView`` exposes NO secret / invite / host identity
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from rapidly.sharing.screen import types as T


class TestCreateScreenSessionRequest:
    def test_defaults(self) -> None:
        req = T.CreateScreenSessionRequest()
        assert req.title is None
        assert req.max_viewers == 10

    def test_title_capped_at_120_chars(self) -> None:
        T.CreateScreenSessionRequest(title="a" * 120)
        with pytest.raises(ValidationError):
            T.CreateScreenSessionRequest(title="a" * 121)

    @pytest.mark.parametrize("bad", [0, -1, 11, 100])
    def test_max_viewers_rejects_out_of_range(self, bad: int) -> None:
        with pytest.raises(ValidationError):
            T.CreateScreenSessionRequest(max_viewers=bad)

    @pytest.mark.parametrize("ok", [1, 5, 10])
    def test_max_viewers_accepts_inclusive_bounds(self, ok: int) -> None:
        assert T.CreateScreenSessionRequest(max_viewers=ok).max_viewers == ok


class TestSecretGatedBodies:
    # MintInviteRequest + CloseSessionRequest share the same secret schema:
    # 1..256 chars. Bundled so a silent divergence (e.g., one side drops
    # the min_length check) is caught uniformly.
    @pytest.mark.parametrize(
        "cls",
        [T.MintInviteRequest, T.CloseSessionRequest],
    )
    def test_empty_secret_is_rejected(self, cls: type) -> None:
        with pytest.raises(ValidationError):
            cls(secret="")

    @pytest.mark.parametrize(
        "cls",
        [T.MintInviteRequest, T.CloseSessionRequest],
    )
    def test_secret_over_256_is_rejected(self, cls: type) -> None:
        with pytest.raises(ValidationError):
            cls(secret="x" * 257)

    @pytest.mark.parametrize(
        "cls",
        [T.MintInviteRequest, T.CloseSessionRequest],
    )
    def test_secret_at_boundary_is_accepted(self, cls: type) -> None:
        cls(secret="x")  # min
        cls(secret="x" * 256)  # max


class TestScreenSessionPublicView:
    def test_has_no_secret_fields(self) -> None:
        # Critical: this model is returned on an UNAUTHENTICATED landing
        # endpoint. Any leak of secret / invite-template would let anyone
        # scraping the landing URL close the session or forge invites.
        fields = set(T.ScreenSessionPublicView.model_fields.keys())
        assert fields == {
            "short_slug",
            "title",
            "max_viewers",
            "started_at",
            "host_connected",
        }
        assert "secret" not in fields
        assert "invite_template" not in fields
        assert "invite_token" not in fields
        assert "long_slug" not in fields
