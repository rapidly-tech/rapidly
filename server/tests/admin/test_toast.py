"""Tests for ``rapidly/admin/toast.py``.

``add_toast`` enqueues ephemeral notifications on the request scope
during handler execution. The admin response pipeline flushes them
via an HTMX out-of-band swap, so multi-toast ordering + the correct
scope key matter. No tests exercised the queue.

Pins:
- Toasts are appended to ``request.scope["toasts"]`` (the documented
  scope key)
- Default variant is ``"info"`` — a silent flip to ``"error"`` would
  make every default-add look like a failure
- FIFO order preserved (handlers enqueue "Step 1" / "Step 2" / …
  and expect them to render in that order)
- First add creates the queue via ``setdefault`` so a subsequent
  ``render_toasts`` call finds it
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest

from rapidly.admin.toast import Toast, add_toast


def _req() -> Any:
    req = MagicMock()
    req.scope = {}
    return req


@pytest.mark.asyncio
class TestAddToast:
    async def test_appends_to_scope_under_toasts_key(self) -> None:
        req = _req()
        await add_toast(req, "saved")
        assert "toasts" in req.scope
        assert [t.message for t in req.scope["toasts"]] == ["saved"]

    async def test_default_variant_is_info(self) -> None:
        # Load-bearing UX pin: un-explicit calls land in the neutral
        # bucket. A regression defaulting to ``error`` would colour
        # every success path red.
        req = _req()
        await add_toast(req, "saved")
        assert req.scope["toasts"][0].variant == "info"

    async def test_explicit_variant_respected(self) -> None:
        req = _req()
        await add_toast(req, "saved", variant="success")
        assert req.scope["toasts"][0].variant == "success"

    async def test_multiple_toasts_preserve_order(self) -> None:
        # Handlers enqueue step-by-step; the render order matches
        # call order so users see the progression.
        req = _req()
        await add_toast(req, "one")
        await add_toast(req, "two", variant="success")
        await add_toast(req, "three", variant="error")
        messages = [(t.message, t.variant) for t in req.scope["toasts"]]
        assert messages == [
            ("one", "info"),
            ("two", "success"),
            ("three", "error"),
        ]

    async def test_setdefault_preserves_existing_queue(self) -> None:
        # If an earlier middleware already seeded the queue, the
        # helper must extend it, not replace it.
        req = _req()
        pre = Toast(message="pre-existing", variant="warning")
        req.scope["toasts"] = [pre]
        await add_toast(req, "new")
        assert len(req.scope["toasts"]) == 2
        assert req.scope["toasts"][0] is pre


class TestToastDataclass:
    def test_uses_slots(self) -> None:
        # ``@dataclass(slots=True)`` — attribute assignment to an
        # unknown field must AttributeError (cheap defensive pin
        # catching a regression that dropped slots).
        t = Toast(message="x", variant="info")
        with pytest.raises(AttributeError):
            t.unknown = "x"  # type: ignore[attr-defined]

    def test_fields(self) -> None:
        t = Toast(message="hello", variant="success")
        assert t.message == "hello"
        assert t.variant == "success"


class TestExports:
    def test_all_surfaces_add_and_render(self) -> None:
        from rapidly.admin import toast as T

        assert set(T.__all__) == {"add_toast", "render_toasts"}
