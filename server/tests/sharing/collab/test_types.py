"""Tests for ``rapidly/sharing/collab/types.py``.

Pins the mesh-cap + kind invariants on the Collab chamber API:
- ``max_participants`` bounded at 2..8 (Yjs bandwidth is cheap but mesh
  connections scale N² — same rationale as Call, with a higher ceiling
  because text CRDT updates are ~30-200 B each).
- ``kind`` Literal["text", "canvas"] — canvas is an optional PR-19
  mode; adding a third kind without Y.Doc schema work would break
  provider bootstrap.
- Secret bounds + public-view leak-prevention mirror the other chambers.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from rapidly.sharing.collab import types as T


class TestCreateCollabSessionRequest:
    def test_defaults(self) -> None:
        req = T.CreateCollabSessionRequest()
        assert req.title is None
        assert req.max_participants == 8
        assert req.kind == "text"

    def test_title_capped_at_120_chars(self) -> None:
        T.CreateCollabSessionRequest(title="a" * 120)
        with pytest.raises(ValidationError):
            T.CreateCollabSessionRequest(title="a" * 121)

    @pytest.mark.parametrize("bad", [0, 1, 9, 16])
    def test_max_participants_rejects_out_of_range(self, bad: int) -> None:
        # 1-participant "collab" is meaningless; >8 blows the mesh budget.
        with pytest.raises(ValidationError):
            T.CreateCollabSessionRequest(max_participants=bad)

    @pytest.mark.parametrize("ok", [2, 4, 8])
    def test_max_participants_accepts_inclusive_bounds(self, ok: int) -> None:
        assert T.CreateCollabSessionRequest(max_participants=ok).max_participants == ok

    def test_kind_rejects_unknown(self) -> None:
        with pytest.raises(ValidationError):
            T.CreateCollabSessionRequest(kind="markdown")  # type: ignore[arg-type]


class TestSecretGatedBodies:
    @pytest.mark.parametrize("cls", [T.MintInviteRequest, T.CloseSessionRequest])
    def test_empty_secret_is_rejected(self, cls: type) -> None:
        with pytest.raises(ValidationError):
            cls(secret="")

    @pytest.mark.parametrize("cls", [T.MintInviteRequest, T.CloseSessionRequest])
    def test_secret_over_256_is_rejected(self, cls: type) -> None:
        with pytest.raises(ValidationError):
            cls(secret="x" * 257)


class TestCollabSessionPublicView:
    def test_has_no_secret_fields(self) -> None:
        fields = set(T.CollabSessionPublicView.model_fields.keys())
        assert fields == {
            "short_slug",
            "title",
            "max_participants",
            "kind",
            "started_at",
            "host_connected",
        }
        assert "secret" not in fields
        assert "invite_template" not in fields
        assert "invite_token" not in fields
        assert "long_slug" not in fields
