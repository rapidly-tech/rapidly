"""Tests for ``rapidly/admin/components/_navigation.py``.

Three load-bearing surfaces:

- Constructor overload: ``str`` route name produces a LEAF (no
  children); ``list[NavigationItem]`` produces a GROUP (no
  ``route_name``). Drift to mix the two would render groups as
  links or vice versa.
- ``_is_active`` priority order: ``active_route_name_prefix`` is
  checked FIRST (prefix match), then exact ``route_name``, then
  recursion into children. Drift to flip this order would either
  miss the prefix's intent (e.g., a "Customers" group would not
  light up on a sub-page) or false-light the parent on unrelated
  pages.
- ``__all__`` exports only ``NavigationItem`` — the rendering side
  is private to the layout component.
"""

from __future__ import annotations

from rapidly.admin.components import _navigation as M
from rapidly.admin.components._navigation import NavigationItem


class TestConstructor:
    def test_str_route_name_creates_leaf(self) -> None:
        # Pin: a string produces a LEAF (route_name set, empty
        # children list).
        item = NavigationItem("Workspaces", "admin.workspaces.list")
        assert item.label == "Workspaces"
        assert item.route_name == "admin.workspaces.list"
        assert item.children == []

    def test_list_creates_group_with_no_route_name(self) -> None:
        # Pin: a list produces a GROUP (route_name=None, children
        # populated). Drift to set route_name on a group would
        # render it as a link AND a <details>/<summary> at once.
        leaf = NavigationItem("Inner", "admin.inner")
        group = NavigationItem("Outer", [leaf])
        assert group.label == "Outer"
        assert group.route_name is None
        assert group.children == [leaf]

    def test_active_route_name_prefix_kwarg_optional(self) -> None:
        # Pin: kwarg defaults to None (no prefix matching). Drift
        # to default-True would mass-light the sidebar.
        item = NavigationItem("X", "admin.x")
        assert item.active_route_name_prefix is None

    def test_active_route_name_prefix_kwarg_set(self) -> None:
        item = NavigationItem(
            "Customers",
            "admin.customers.list",
            active_route_name_prefix="admin.customers.",
        )
        assert item.active_route_name_prefix == "admin.customers."


class TestIsActivePriority:
    def test_prefix_takes_precedence_over_route_name(self) -> None:
        # Pin: when ``active_route_name_prefix`` is set, we use
        # prefix matching INSTEAD of exact route_name compare.
        # Drift would un-light the parent on sub-pages.
        item = NavigationItem(
            "Customers",
            "admin.customers.list",
            active_route_name_prefix="admin.customers.",
        )
        # Sub-page route name → still active because prefix matches.
        assert item._is_active("admin.customers.detail") is True
        # Unrelated route → not active.
        assert item._is_active("admin.workspaces.list") is False

    def test_exact_route_name_match_when_no_prefix(self) -> None:
        # Pin: without a prefix, only EXACT match lights up. Drift
        # to startswith would false-light unrelated routes.
        item = NavigationItem("Workspaces", "admin.workspaces")
        assert item._is_active("admin.workspaces") is True
        assert item._is_active("admin.workspaces.list") is False

    def test_group_active_when_any_child_active(self) -> None:
        # Pin: group has no route_name; activates when ANY child
        # matches. Drift to require ALL children would never light
        # up a group.
        a = NavigationItem("A", "admin.a")
        b = NavigationItem("B", "admin.b")
        group = NavigationItem("Group", [a, b])
        assert group._is_active("admin.a") is True
        assert group._is_active("admin.b") is True
        assert group._is_active("admin.c") is False

    def test_group_recurses_into_nested_children(self) -> None:
        # Pin: recursion goes deeper than one level. A grandchild
        # match still activates the top-level group.
        leaf = NavigationItem("Leaf", "admin.deep.leaf")
        mid = NavigationItem("Mid", [leaf])
        top = NavigationItem("Top", [mid])
        assert top._is_active("admin.deep.leaf") is True

    def test_inactive_group_when_no_children_match(self) -> None:
        a = NavigationItem("A", "admin.a")
        b = NavigationItem("B", "admin.b")
        group = NavigationItem("Group", [a, b])
        assert group._is_active("admin.unrelated") is False


class TestExports:
    def test_dunder_all_pinned(self) -> None:
        # Pin: only ``NavigationItem`` is publicly exported. The
        # render method is exposed only via the instance, not the
        # module, so refactors of the rendering pipeline don't
        # leak into callers.
        assert M.__all__ == ["NavigationItem"]
