"""Tests for ``rapidly.projects.common`` — the shared HexColor validator.

The hex-colour pattern is load-bearing because every project entity
renders ``color`` straight into a CSS value in the UI.  Drift to a
laxer regex (or removing it entirely) would let an attacker persist
``"javascript:alert(1)"`` as a colour and execute it inside a
:style attribute on the dashboard.
"""

from __future__ import annotations

import pytest
from pydantic import BaseModel, ValidationError

from rapidly.projects.common import HexColor, OptionalHexColor


class _Required(BaseModel):
    color: HexColor


class _Optional(BaseModel):
    color: OptionalHexColor = None


class TestHexColorRequired:
    @pytest.mark.parametrize(
        "value",
        [
            "#000000",
            "#FFFFFF",
            "#abc123",
            "#abcdef12",  # 8-digit (rgba)
        ],
    )
    def test_accepts_valid_hex(self, value: str) -> None:
        assert _Required(color=value).color == value

    @pytest.mark.parametrize(
        "value",
        [
            "javascript:alert(1)",
            "red",
            "#GGG000",
            "#fff",  # short form not accepted (deliberately narrow)
            "000000",
            "#",
            "#0000000",  # 7 chars — neither 6 nor 8
            "",
        ],
    )
    def test_rejects_invalid(self, value: str) -> None:
        # Pin: every non-hex value MUST raise.  Drift would allow
        # arbitrary strings to land in a CSS context.
        with pytest.raises(ValidationError):
            _Required(color=value)


class TestOptionalHexColor:
    def test_none_is_allowed(self) -> None:
        assert _Optional(color=None).color is None
        assert _Optional().color is None

    def test_valid_hex_passes(self) -> None:
        assert _Optional(color="#6b7280").color == "#6b7280"

    def test_invalid_still_rejected(self) -> None:
        with pytest.raises(ValidationError):
            _Optional(color="not-a-color")
