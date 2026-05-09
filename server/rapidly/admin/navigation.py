"""Sidebar menu entries for the Rapidly admin panel.

Each :class:`NavigationItem` maps a label to a FastAPI route name and
an optional prefix used for active-state highlighting.  The list is
consumed by the layout component to render the sidebar.
"""

from .components import navigation

# Sidebar items are declared top-to-bottom in display order.  The
# ``active_route_name_prefix`` lets an entire route family (e.g.
# everything under ``users:``) highlight the same menu entry.

NAVIGATION = [
    navigation.NavigationItem(
        "Users",
        "users:list",
        active_route_name_prefix="users:",
    ),
    navigation.NavigationItem(
        "Workspaces",
        "workspaces:list",
        active_route_name_prefix="workspaces:",
    ),
    navigation.NavigationItem(
        "Customers",
        "customers:list",
        active_route_name_prefix="customers:",
    ),
    navigation.NavigationItem(
        "Products",
        "shares:list",
        active_route_name_prefix="shares:",
    ),
    navigation.NavigationItem(
        "External Events",
        "external_events:list",
        active_route_name_prefix="external_events:",
    ),
    navigation.NavigationItem(
        "File Sharing",
        "file_sharing:list",
        active_route_name_prefix="file_sharing:",
    ),
    navigation.NavigationItem(
        "Tasks",
        "tasks:list",
        active_route_name_prefix="tasks:",
    ),
    navigation.NavigationItem(
        "Webhooks",
        "webhooks:list",
        active_route_name_prefix="webhooks:",
    ),
]
