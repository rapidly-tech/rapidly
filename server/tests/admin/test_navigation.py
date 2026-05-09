"""Tests for ``rapidly/admin/navigation.py`` + ``components/_navigation.py``.

Admin sidebar navigation. Three load-bearing surfaces:

- ``NavigationItem`` constructor accepts either a route-name string
  (leaf) OR a list of child items (group). The two forms must NOT
  cross-contaminate (a leaf with .children, or a group with
  .route_name) — drift would let the renderer pick the wrong
  branch and either skip the link or render a phantom group.
- ``_is_active`` precedence: ``active_route_name_prefix`` wins
  over exact ``route_name`` match. Drift would let a route
  family lose its sidebar highlight when a child is active.
- ``NAVIGATION`` is the documented top-level sidebar order.
  Adding / removing entries silently changes the admin UX —
  pin the count and the display labels so a reorganisation
  surfaces in code review.
"""

from __future__ import annotations

from rapidly.admin.components._navigation import NavigationItem
from rapidly.admin.navigation import NAVIGATION


class TestNavigationItemLeaf:
    def test_string_argument_creates_leaf(self) -> None:
        # Pin: passing a string sets route_name and leaves
        # children as empty list (the renderer's leaf branch).
        item = NavigationItem("Users", "users:list")
        assert item.label == "Users"
        assert item.route_name == "users:list"
        assert item.children == []

    def test_active_prefix_optional(self) -> None:
        # Pin: ``active_route_name_prefix`` is keyword-only and
        # optional. Drift to required would break callers that
        # don't need a prefix.
        item = NavigationItem("X", "x:list")
        assert item.active_route_name_prefix is None


class TestNavigationItemGroup:
    def test_list_argument_creates_group(self) -> None:
        # Pin: passing a list sets children and clears route_name
        # (the renderer's group branch).
        leaf = NavigationItem("Child", "child:list")
        group = NavigationItem("Parent", [leaf])
        assert group.route_name is None
        assert group.children == [leaf]


class TestNavigationItemIsActive:
    def test_prefix_match_wins(self) -> None:
        # Pin: when ``active_route_name_prefix`` is set, ANY
        # current_route starting with the prefix highlights the
        # entry. Drift would let a route family (e.g.
        # users:detail, users:edit) lose its sidebar highlight.
        item = NavigationItem("Users", "users:list", active_route_name_prefix="users:")
        assert item._is_active("users:list") is True
        assert item._is_active("users:detail") is True
        assert item._is_active("users:edit") is True
        assert item._is_active("workspaces:list") is False

    def test_exact_route_match_when_no_prefix(self) -> None:
        # Pin: without a prefix, only exact route_name match
        # highlights. Drift to substring match would over-
        # highlight (e.g., ``users`` highlighting also for
        # ``users_admin``).
        item = NavigationItem("Users", "users:list")
        assert item._is_active("users:list") is True
        assert item._is_active("users:detail") is False

    def test_group_active_when_any_child_active(self) -> None:
        # Pin: group highlight is the OR of its children. Drift
        # would either over- or under-highlight expandable
        # sections.
        child1 = NavigationItem("A", "a:list")
        child2 = NavigationItem("B", "b:list")
        group = NavigationItem("Parent", [child1, child2])
        assert group._is_active("a:list") is True
        assert group._is_active("b:list") is True
        assert group._is_active("c:list") is False

    def test_inactive_when_no_match(self) -> None:
        item = NavigationItem("Users", "users:list")
        assert item._is_active("workspaces:list") is False


class TestNavigationOrderAndCount:
    def test_pinned_at_eight_entries(self) -> None:
        # Pin: 8 sidebar items. Adding / removing silently
        # changes the admin UX — drift here surfaces in code
        # review.
        assert len(NAVIGATION) == 8

    def test_display_order_pinned(self) -> None:
        # Pin: the documented top-to-bottom order. Drift would
        # silently re-order the sidebar (admin muscle memory
        # regression).
        assert [item.label for item in NAVIGATION] == [
            "Users",
            "Workspaces",
            "Customers",
            "Products",
            "External Events",
            "File Sharing",
            "Tasks",
            "Webhooks",
        ]

    def test_every_entry_has_route_name(self) -> None:
        # Pin: every top-level entry is a LEAF (NOT a group).
        # The current admin doesn't use group-style nesting at
        # the top level; drift to a group would change the
        # rendering branch and break the Tailwind classes.
        for item in NAVIGATION:
            assert item.route_name is not None
            assert item.children == []

    def test_every_entry_has_active_route_prefix(self) -> None:
        # Pin: every entry uses prefix-based active-state
        # detection. Drift to exact-match-only would lose the
        # sidebar highlight when on a sub-page (e.g., user
        # detail page wouldn't highlight the Users entry).
        for item in NAVIGATION:
            assert item.active_route_name_prefix is not None

    def test_active_prefixes_match_route_name_prefixes(self) -> None:
        # Pin: each prefix matches the route_name's prefix.
        # Drift would mean the entry would never highlight on
        # its own list page.
        for item in NAVIGATION:
            assert item.route_name is not None
            assert item.active_route_name_prefix is not None
            assert item.route_name.startswith(item.active_route_name_prefix)


class TestExports:
    def test_navigation_item_exported(self) -> None:
        # Pin the public API.
        from rapidly.admin.components import _navigation

        assert _navigation.__all__ == ["NavigationItem"]
