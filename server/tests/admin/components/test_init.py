"""Tests for ``rapidly/admin/components/__init__.py``.

The components package re-exports every shared UI primitive so
consuming modules can do ``from ..components import button``.

Two load-bearing surfaces:

- ``__all__`` is the documented public API of the package. Drift
  to drop a name silently breaks every importer; drift to add a
  name without a corresponding submodule export silently surfaces
  internal helpers.
- Every name in ``__all__`` is actually importable from the
  package — defensive against a regression that re-exported a
  name without importing its source.
"""

from __future__ import annotations

import importlib

from rapidly.admin import components as M


class TestComponentsPublicApi:
    def test_dunder_all_pinned(self) -> None:
        # Pin: 19 documented public names. Drift here surfaces in
        # code review (any new component must be added explicitly).
        assert set(M.__all__) == {
            "Tab",
            "accordion",
            "action_bar",
            "alert",
            "button",
            "card",
            "clipboard_button",
            "confirmation_dialog",
            "datatable",
            "description_list",
            "empty_state",
            "identity_verification_status_badge",
            "input",
            "layout",
            "loading_state",
            "metric_card",
            "modal",
            "navigation",
            "status_badge",
            "tab_nav",
        }

    def test_all_is_sorted(self) -> None:
        # Pin: alphabetical order so diffs are minimal when adding
        # a new component.
        assert M.__all__ == sorted(M.__all__)

    def test_every_name_in_all_is_importable(self) -> None:
        # Pin: every advertised name actually exists on the
        # package. Drift to remove the underlying submodule
        # without updating __all__ would surface here.
        package = importlib.import_module("rapidly.admin.components")
        for name in M.__all__:
            assert hasattr(package, name), f"missing export: {name}"


class TestLayoutExport:
    def test_layout_module_exports_layout(self) -> None:
        # Pin: ``layout`` context manager exported from the
        # _layout submodule.
        from rapidly.admin.components import _layout

        assert _layout.__all__ == ["layout"]

    def test_layout_callable_at_components_root(self) -> None:
        # Pin: the layout context manager is reachable via the
        # package shortcut. Used by every admin page.
        from rapidly.admin.components import layout

        assert callable(layout)


class TestSubmoduleAliasing:
    def test_accordion_alias(self) -> None:
        # Pin: ``accordion`` alias points at the _accordion
        # submodule (callers do ``components.accordion.item(...)``).
        from rapidly.admin.components import _accordion

        assert M.accordion is _accordion

    def test_datatable_alias(self) -> None:
        from rapidly.admin.components import _datatable

        assert M.datatable is _datatable

    def test_description_list_alias(self) -> None:
        from rapidly.admin.components import _description_list

        assert M.description_list is _description_list

    def test_input_alias(self) -> None:
        from rapidly.admin.components import _input

        assert M.input is _input

    def test_navigation_alias(self) -> None:
        from rapidly.admin.components import _navigation

        assert M.navigation is _navigation
