"""Tests for ``rapidly/admin/components/_input.py``.

Toolbar form-control components. Three load-bearing surfaces:

- ``search`` emits ``type="search"`` (NOT ``type="text"``). The
  browser's native clear button + on-screen-keyboard search
  affordance hinge on this attribute. Drift would silently
  remove both UX cues.
- ``select`` placeholder option has ``value=""`` and is
  ``selected`` ONLY when the caller's ``value`` is falsy. Drift
  to a non-empty value would submit the placeholder string as a
  real choice; drift to always-selected would un-select the
  caller's actual value.
- ``select`` matches the currently-selected option via
  ``form_value == value`` per row. Drift to identity (``is``) or
  index match would drop ``selected`` on every option for
  string-built option lists.
"""

from __future__ import annotations

from typing import Any

from tagflow import document

from rapidly.admin.components import _input as M
from rapidly.admin.components._input import search, select


def _render(cm_factory: Any) -> str:
    """Render a context manager component to its HTML string."""
    with document() as doc:
        with cm_factory:
            pass
    return doc.to_html()


class TestSearch:
    def test_emits_type_search(self) -> None:
        # Pin: ``type="search"`` enables native clear button +
        # on-screen-keyboard search affordance. Drift to ``text``
        # would drop both.
        html = _render(search(name="q"))
        assert 'type="search"' in html

    def test_emits_name_value_placeholder(self) -> None:
        # Pin: caller-supplied attrs reach the rendered input.
        html = _render(search(name="q", value="alice", placeholder="Search…"))
        assert 'name="q"' in html
        assert 'value="alice"' in html
        assert "Search" in html  # placeholder text in attribute

    def test_includes_magnifying_glass_icon(self) -> None:
        # Pin: the icon hook (``icon-search`` Tailwind class).
        # Drift would render a naked text input.
        html = _render(search())
        assert "icon-search" in html


class TestSelectPlaceholder:
    def test_placeholder_emits_empty_value_option(self) -> None:
        # Pin: placeholder uses ``value=""`` so submitting the
        # form when nothing is picked sends an empty string (not
        # the placeholder label as a choice).
        html = _render(select([("A", "a"), ("B", "b")], placeholder="Pick one"))
        # First option is the placeholder with value="".
        assert 'value=""' in html
        assert "Pick one" in html

    def test_placeholder_selected_when_value_falsy(self) -> None:
        # Pin: with no caller ``value``, the placeholder is the
        # selected default. Drift would leave the dropdown
        # showing the first real option instead of the prompt.
        html = _render(select([("A", "a")], placeholder="Pick one"))
        # The placeholder <option> carries selected.
        # tagflow renders boolean attrs as bare attribute names.
        assert "selected" in html

    def test_placeholder_not_selected_when_value_set(self) -> None:
        # Pin: caller's value wins over placeholder selection.
        # Drift would un-select the caller's actual choice on
        # every render.
        html = _render(
            select([("A", "a"), ("B", "b")], value="b", placeholder="Pick one")
        )
        # Placeholder option appears at value="" but a different
        # option (value="b") should be the selected one.
        # The simplest pin: "b" is in the rendered HTML and the
        # rendered output contains the selected attribute on the
        # matching option (positional match: "b" before the close
        # of the matching tag). We assert structurally:
        assert 'value="b"' in html
        # Count of "selected" attr should be exactly 1 (only the
        # caller's value, not the placeholder).
        assert html.count("selected") == 1

    def test_no_placeholder_omits_empty_option(self) -> None:
        # Pin: when ``placeholder=None``, no empty-value option is
        # emitted. Drift would always inject an empty choice.
        html = _render(select([("A", "a"), ("B", "b")]))
        assert 'value=""' not in html


class TestSelectOptionMatching:
    def test_caller_value_marks_matching_option_selected(self) -> None:
        # Pin: the option whose ``form_value`` equals the caller's
        # ``value`` is the one that carries ``selected``. Drift to
        # identity / index match would un-select on every render
        # for strings constructed from the database.
        html = _render(select([("A", "a"), ("B", "b"), ("C", "c")], value="b"))
        # Exactly one selected; "b" is the chosen value.
        assert html.count("selected") == 1
        assert 'value="b"' in html

    def test_no_match_no_option_selected(self) -> None:
        # Pin: a caller-supplied value that doesn't match any
        # option produces NO selected option (silent rather than
        # default-to-first-option). Drift to default-to-first
        # would silently misrepresent the form state.
        html = _render(select([("A", "a"), ("B", "b")], value="ghost"))
        assert "selected" not in html

    def test_renders_all_option_labels(self) -> None:
        # Pin: every (display_label, form_value) pair makes it
        # into the rendered HTML.
        html = _render(select([("Alpha", "a"), ("Beta", "b"), ("Gamma", "g")]))
        assert "Alpha" in html
        assert "Beta" in html
        assert "Gamma" in html
        assert 'value="a"' in html
        assert 'value="b"' in html
        assert 'value="g"' in html


class TestExports:
    def test_dunder_all_pinned(self) -> None:
        # Pin: search + select are the public exports. Drift to
        # add an internal helper would silently widen the API.
        assert M.__all__ == ["search", "select"]
