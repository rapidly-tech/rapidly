"""Rapidly admin panel component library.

Re-exports every shared UI primitive so that consuming modules can do::

    from ..components import button, datatable, modal
"""

from . import _accordion as accordion
from . import _datatable as datatable
from . import _description_list as description_list
from . import _input as input
from . import _navigation as navigation
from ._action_bar import action_bar
from ._alert import alert
from ._button import button
from ._clipboard_button import clipboard_button
from ._confirmation_dialog import confirmation_dialog
from ._layout import layout
from ._metric_card import metric_card
from ._modal import modal
from ._state import card, empty_state, loading_state
from ._status_badge import identity_verification_status_badge, status_badge
from ._tab_nav import Tab, tab_nav

__all__ = [
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
]
