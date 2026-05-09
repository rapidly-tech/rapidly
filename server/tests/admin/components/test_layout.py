"""Tests for ``rapidly/admin/components/_layout.py``.

The admin page-shell dispatcher. Two load-bearing surfaces:

- HTMX-boosted partial detection — ONLY when BOTH
  ``HX-Boosted`` and ``HX-Target == "content"`` headers are
  present, the layout takes the fast path: content + title +
  menu (no outer shell). Drift to either require only one or
  AND-flip the check would either re-render the chrome on every
  click (boost broken) or render the partial in the wrong
  context (HTMX can't find the swap target).
- Full-page render path uses ``base(...)`` for the document
  shell; the partial path does NOT call ``base`` (otherwise the
  HTML, head, and stylesheets would re-emit on every nav).
- ``__all__`` exports only ``layout``; ``content`` and ``menu``
  stay private — they are partials reserved for the dispatcher.
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import Any
from unittest.mock import MagicMock

import pytest
from tagflow import document

from rapidly.admin.components import _layout as M


def _request(headers: dict[str, str] | None = None) -> Any:
    """Build a fake ``Request`` whose ``headers`` is the given dict and
    whose ``url_for`` echoes its name as a fake URL."""
    req = MagicMock()
    req.headers = headers or {}
    req.url_for.side_effect = lambda *args, **kwargs: f"/url/{args[0] if args else ''}"
    return req


@pytest.fixture
def collaborators(monkeypatch: pytest.MonkeyPatch) -> dict[str, MagicMock]:
    """Replace the layout's collaborators (``base``, ``content``,
    ``menu``, ``title``) with recording context managers so we can
    assert which path the dispatcher took.
    """
    calls: dict[str, MagicMock] = {}

    for name in ("base", "content", "menu", "title"):
        recorder = MagicMock(name=name)

        @contextmanager
        def _cm(*args: Any, _recorder: MagicMock = recorder, **kwargs: Any) -> Any:
            _recorder(*args, **kwargs)
            yield

        monkeypatch.setattr(M, name, _cm)
        calls[name] = recorder

    return calls


class TestPartialPath:
    def test_boosted_with_target_content_skips_shell(
        self, collaborators: dict[str, MagicMock]
    ) -> None:
        # Pin: BOTH ``HX-Boosted`` and ``HX-Target == "content"``
        # headers → partial path. Drift would either double-render
        # the shell on every click or render the partial wrongly.
        req = _request({"HX-Boosted": "true", "HX-Target": "content"})

        with M.layout(req, [("Page", "/admin/page")], [], "admin.page"):
            pass

        # Partial path: content + title + menu, NO base shell.
        assert collaborators["content"].called
        assert collaborators["title"].called
        assert collaborators["menu"].called
        assert not collaborators["base"].called

    def test_partial_path_uses_breadcrumb_labels_for_title(
        self, collaborators: dict[str, MagicMock]
    ) -> None:
        # Pin: page <title> is built from the breadcrumb labels
        # (most-specific first). Drift would emit a stale title
        # on partial swaps.
        req = _request({"HX-Boosted": "true", "HX-Target": "content"})

        with M.layout(
            req,
            [("Detail", "/x/1"), ("Resources", "/x")],
            [],
            "admin.x.detail",
        ):
            pass

        title_args, _ = collaborators["title"].call_args
        assert title_args[0] == ["Detail", "Resources"]


class TestFullPagePath:
    def test_no_headers_renders_full_shell(
        self, collaborators: dict[str, MagicMock]
    ) -> None:
        # Pin: with no HTMX headers, the full document shell
        # renders (``base`` is called).
        req = _request({})

        with document(), M.layout(req, [("Page", "/admin/page")], [], "admin.page"):
            pass

        assert collaborators["base"].called
        # Full path also still renders content + menu.
        assert collaborators["content"].called
        assert collaborators["menu"].called

    def test_boosted_without_target_falls_through_to_full(
        self, collaborators: dict[str, MagicMock]
    ) -> None:
        # Pin: ``HX-Boosted`` alone is not enough — the target
        # must also be ``content``. Drift to take the partial
        # path here would mismatch the OOB swap target.
        req = _request({"HX-Boosted": "true"})

        with document(), M.layout(req, [("X", "/x")], [], "admin.x"):
            pass

        assert collaborators["base"].called

    def test_target_content_without_boost_falls_through_to_full(
        self, collaborators: dict[str, MagicMock]
    ) -> None:
        # Pin: HX-Target alone doesn't trigger partial — only
        # boosted clicks should produce the partial response.
        req = _request({"HX-Target": "content"})

        with document(), M.layout(req, [("X", "/x")], [], "admin.x"):
            pass

        assert collaborators["base"].called

    def test_target_other_than_content_falls_through_to_full(
        self, collaborators: dict[str, MagicMock]
    ) -> None:
        # Pin: ``HX-Target`` must be exactly ``content`` (matching
        # the ``id="content"`` div in the full shell). Any other
        # value → full render. Drift would mismatch the swap.
        req = _request({"HX-Boosted": "true", "HX-Target": "sidebar"})

        with document(), M.layout(req, [("X", "/x")], [], "admin.x"):
            pass

        assert collaborators["base"].called


class TestExports:
    def test_dunder_all_pinned(self) -> None:
        # Pin: only ``layout`` is publicly exported. ``content``
        # and ``menu`` stay private partials of the dispatcher.
        assert M.__all__ == ["layout"]
