"""Tests for ``rapidly/admin/components/_status_badge.py``.

Status-badge style mapping. Three load-bearing surfaces:

- ``_STATUS_STYLES`` covers every ``WorkspaceStatus`` member with
  a (CSS class, aria-label) tuple. Drift to add a new status
  without a style would render via ``_FALLBACK_STYLE`` (silent
  loss of brand colour) — pin coverage so any new status surfaces
  in code review.
- The two ``_REVIEW`` statuses (initial / ongoing) get
  ``badge-warning`` (amber). Drift would silently downgrade the
  visual urgency of pending-review workspaces.
- ``_FALLBACK_STYLE`` is a safe ghost+border colour with
  "unknown status" aria — a defence-in-depth default for any
  missing status.
"""

from __future__ import annotations

from rapidly.admin.components._status_badge import (
    _FALLBACK_STYLE,
    _STATUS_STYLES,
)
from rapidly.models.workspace import WorkspaceStatus


class TestStatusStyles:
    def test_every_status_has_a_style(self) -> None:
        # Pin: every WorkspaceStatus enum member has a mapping.
        # Drift to add a new status without a style would render
        # via _FALLBACK_STYLE (silent loss of brand colour).
        for status in WorkspaceStatus:
            assert status in _STATUS_STYLES, f"missing style for {status}"

    def test_active_uses_ghost_with_border(self) -> None:
        # Pin: active workspaces use the documented ghost+border
        # treatment. Drift would change every active workspace's
        # appearance in the admin.
        cls, _aria = _STATUS_STYLES[WorkspaceStatus.ACTIVE]
        assert "badge-ghost" in cls
        assert "border" in cls

    def test_review_statuses_use_warning_amber(self) -> None:
        # Pin: BOTH initial and ongoing review use badge-warning.
        # Drift would silently downgrade the visual urgency of
        # pending-review workspaces.
        cls_initial, _ = _STATUS_STYLES[WorkspaceStatus.INITIAL_REVIEW]
        cls_ongoing, _ = _STATUS_STYLES[WorkspaceStatus.ONGOING_REVIEW]
        assert cls_initial == "badge-warning"
        assert cls_ongoing == "badge-warning"

    def test_aria_labels_pinned(self) -> None:
        # Pin: aria-label phrasing — screen readers read these
        # literally to admin operators (a11y).
        assert _STATUS_STYLES[WorkspaceStatus.ACTIVE][1] == "active status"
        assert (
            _STATUS_STYLES[WorkspaceStatus.INITIAL_REVIEW][1] == "initial review status"
        )
        assert (
            _STATUS_STYLES[WorkspaceStatus.ONGOING_REVIEW][1] == "ongoing review status"
        )
        assert _STATUS_STYLES[WorkspaceStatus.DENIED][1] == "denied status"


class TestFallbackStyle:
    def test_fallback_uses_ghost_with_border(self) -> None:
        # Pin: defensive default for any unknown status. Same
        # ghost+border as ACTIVE so the admin doesn't render an
        # eye-catching colour for a status we don't recognise.
        cls, aria = _FALLBACK_STYLE
        assert "badge-ghost" in cls
        assert "border" in cls

    def test_fallback_aria_unknown(self) -> None:
        # Pin: aria-label says "unknown status" so screen-reader
        # users know the visual treatment is a fallback.
        _cls, aria = _FALLBACK_STYLE
        assert aria == "unknown status"
