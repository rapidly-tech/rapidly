"""Tests for ``rapidly/admin/components/_tab_nav.py``.

Two load-bearing surfaces:

- ``Tab`` dataclass shape + ``slots=True`` (memory-cheap when
  many tabs are rendered). Pin defaults: ``active=False``,
  ``count=None``, ``url=None``, ``badge_variant=None``.
- ``__all__`` exports ``Tab`` + ``tab_nav`` — drift would break
  every admin detail page.
"""

from __future__ import annotations

from rapidly.admin.components import _tab_nav as M
from rapidly.admin.components._tab_nav import Tab


class TestTabDataclass:
    def test_label_required(self) -> None:
        # Pin: label is the only required field.
        tab = Tab(label="Overview")
        assert tab.label == "Overview"

    def test_default_field_values(self) -> None:
        # Pin: documented defaults. Drift to required would break
        # callers that only set the label.
        tab = Tab(label="X")
        assert tab.url is None
        assert tab.active is False
        assert tab.count is None
        assert tab.badge_variant is None

    def test_is_slotted(self) -> None:
        # Pin: slots=True. Many tabs per detail page; without
        # slots each Tab carries a __dict__.
        tab = Tab(label="X")
        assert not hasattr(tab, "__dict__")

    def test_all_fields_settable(self) -> None:
        # Pin field set: label / url / active / count /
        # badge_variant.
        tab = Tab(
            label="Settings",
            url="/admin/x/settings",
            active=True,
            count=3,
            badge_variant="warning",
        )
        assert tab.label == "Settings"
        assert tab.url == "/admin/x/settings"
        assert tab.active is True
        assert tab.count == 3
        assert tab.badge_variant == "warning"


class TestExports:
    def test_dunder_all_pinned(self) -> None:
        # Pin: Tab dataclass + tab_nav function exported.
        assert M.__all__ == ["Tab", "tab_nav"]
