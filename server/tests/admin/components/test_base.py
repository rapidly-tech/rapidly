"""Tests for ``rapidly/admin/components/_base.py``.

Page-shell constants. Three load-bearing surfaces:

- ``_TITLE_SUFFIX`` = "Rapidly Admin panel" — appears in every
  browser tab. Drift would silently rebrand the admin.
- ``_GLOBAL_HYPERSCRIPT`` carries the auto-disable-submit-button
  behaviour (prevents double-submits during in-flight HTMX
  requests) AND the CopyToClipboard behaviour. Drift to remove
  the auto-disable would re-enable double-submit on every form.
- ``_SPINNER_HYPERSCRIPT`` toggles the activity spinner via
  HTMX events (``beforeSend`` / ``afterOnLoad`` /
  ``historyRestore``). Drift to remove an event would either
  leave the spinner stuck on / never show it.
"""

from __future__ import annotations

from rapidly.admin.components import _base as M
from rapidly.admin.components._base import (
    _GLOBAL_HYPERSCRIPT,
    _SPINNER_HYPERSCRIPT,
    _TITLE_SUFFIX,
)


class TestTitleSuffix:
    def test_pinned(self) -> None:
        # Pin: brand suffix on every tab title. Drift = silent
        # admin rebrand.
        assert _TITLE_SUFFIX == "Rapidly Admin panel"


class TestGlobalHyperscript:
    def test_disables_submit_buttons_during_request(self) -> None:
        # Pin: the auto-disable behaviour on form submission.
        # Drift to remove would let users double-submit during
        # an in-flight HTMX request (duplicate writes).
        assert "htmx:beforeSend from <form />" in _GLOBAL_HYPERSCRIPT
        assert "submitButton" in _GLOBAL_HYPERSCRIPT
        assert "toggle @disabled on submitButton" in _GLOBAL_HYPERSCRIPT

    def test_copy_to_clipboard_behavior_present(self) -> None:
        # Pin: clipboard_button.py installs this behaviour by name.
        # Drift to rename or drop it would silently break every
        # copy button in the admin.
        assert "behavior CopyToClipboard(text)" in _GLOBAL_HYPERSCRIPT
        assert "navigator.clipboard.writeText(text)" in _GLOBAL_HYPERSCRIPT

    def test_copy_button_toggles_icon_for_5s(self) -> None:
        # Pin: 5-second visual-feedback duration. Drift to a
        # shorter time would feel flickery; longer would feel
        # broken (button stuck disabled).
        assert "wait 5s" in _GLOBAL_HYPERSCRIPT


class TestSpinnerHyperscript:
    def test_shows_on_before_send(self) -> None:
        # Pin: HTMX request start → show spinner.
        assert "htmx:beforeSend" in _SPINNER_HYPERSCRIPT
        assert "remove .hidden" in _SPINNER_HYPERSCRIPT

    def test_hides_on_after_load(self) -> None:
        # Pin: HTMX request finish → hide spinner.
        assert "htmx:afterOnLoad" in _SPINNER_HYPERSCRIPT

    def test_hides_on_history_restore(self) -> None:
        # Pin: browser back/forward → hide spinner. Drift would
        # leave the spinner stuck on after navigation.
        assert "htmx:historyRestore" in _SPINNER_HYPERSCRIPT


class TestExports:
    def test_dunder_all_pinned(self) -> None:
        # Pin: only ``base`` + ``title`` are publicly exported.
        assert M.__all__ == ["base", "title"]
