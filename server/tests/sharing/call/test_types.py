"""Tests for ``rapidly/sharing/call/types.py``.

Pins the mesh-cap + mode invariants on the Call chamber API:
- ``max_participants`` bounded at 2..4 (N² peer-connection count on home
  uplinks — raising this cap without touching the mesh coordinator would
  silently melt guests on 10 Mbit uplinks).
- ``mode`` Literal["audio_only", "audio_video"] — adding a new mode
  without updating the browser's ``getUserMedia`` flow would strand
  clients.
- Secret bounds + public-view leak-prevention mirror the other chambers.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from rapidly.sharing.call import types as T


class TestCreateCallSessionRequest:
    def test_defaults(self) -> None:
        req = T.CreateCallSessionRequest()
        assert req.title is None
        assert req.max_participants == 4
        assert req.mode == "audio_video"

    def test_title_capped_at_120_chars(self) -> None:
        T.CreateCallSessionRequest(title="a" * 120)
        with pytest.raises(ValidationError):
            T.CreateCallSessionRequest(title="a" * 121)

    @pytest.mark.parametrize("bad", [0, 1, 5, 10])
    def test_max_participants_rejects_out_of_range(self, bad: int) -> None:
        # 1-participant "call" is meaningless; >4 blows the mesh budget.
        with pytest.raises(ValidationError):
            T.CreateCallSessionRequest(max_participants=bad)

    @pytest.mark.parametrize("ok", [2, 3, 4])
    def test_max_participants_accepts_inclusive_bounds(self, ok: int) -> None:
        assert T.CreateCallSessionRequest(max_participants=ok).max_participants == ok

    def test_mode_rejects_unknown(self) -> None:
        with pytest.raises(ValidationError):
            T.CreateCallSessionRequest(mode="video_only")  # type: ignore[arg-type]


class TestSecretGatedBodies:
    @pytest.mark.parametrize("cls", [T.MintInviteRequest, T.CloseSessionRequest])
    def test_empty_secret_is_rejected(self, cls: type) -> None:
        with pytest.raises(ValidationError):
            cls(secret="")

    @pytest.mark.parametrize("cls", [T.MintInviteRequest, T.CloseSessionRequest])
    def test_secret_over_256_is_rejected(self, cls: type) -> None:
        with pytest.raises(ValidationError):
            cls(secret="x" * 257)


class TestCallSessionPublicView:
    def test_has_no_secret_fields(self) -> None:
        fields = set(T.CallSessionPublicView.model_fields.keys())
        assert fields == {
            "short_slug",
            "title",
            "max_participants",
            "mode",
            "started_at",
            "host_connected",
        }
        assert "secret" not in fields
        assert "invite_template" not in fields
        assert "invite_token" not in fields
        assert "long_slug" not in fields
