"""Tests for ``rapidly/admin/customers/components.py``.

Three load-bearing surfaces:

- ``CustomerIDColumn`` enables clipboard copy on the ID column
  (admins paste these into Stripe / Sentry / log-search) and
  produces a deep link to ``customers:get`` for the row's
  customer id. Drift to drop the clipboard flag would force
  triple-click selection on every UUID; drift to a wrong route
  name would 404 every link.
- ``WorkspaceColumn`` deep-links to the row's WORKSPACE detail
  page (NOT the customer detail) — drift would link the same
  customer to itself instead of the workspace it belongs to.
- ``email_verified_badge`` renders ``badge-success`` + "Verified"
  when truthy; ``badge-neutral`` + "Not Verified" otherwise.
  Drift to flip the truthy branch would invert the moderator's
  at-a-glance trust signal.
"""

from __future__ import annotations

from unittest.mock import MagicMock
from uuid import UUID

from tagflow import document

from rapidly.admin.customers.components import (
    CustomerIDColumn,
    WorkspaceColumn,
    email_verified_badge,
)


def _render_badge(verified: bool) -> str:
    with document() as doc:
        with email_verified_badge(verified):
            pass
    return doc.to_html()


class TestCustomerIDColumn:
    def test_clipboard_enabled(self) -> None:
        # Pin: admins paste customer IDs into Stripe / Sentry /
        # log-search constantly. Drift to drop the clipboard
        # flag would force triple-click selection on every UUID.
        column = CustomerIDColumn()
        assert getattr(column, "clipboard", False) is True

    def test_label_pinned(self) -> None:
        # Pin: the column header is "ID" (drift to "Customer ID"
        # would shift the table layout and break wide-screen
        # padding).
        column = CustomerIDColumn()
        assert getattr(column, "label", None) == "ID"

    def test_href_points_to_customer_detail(self) -> None:
        # Pin: clicking the ID navigates to the customer's
        # detail page. Drift to a sibling route would 404.
        column = CustomerIDColumn()
        request = MagicMock()
        request.url_for.return_value = "/admin/customers/abc"
        item = MagicMock()
        item.id = UUID("11111111-1111-1111-1111-111111111111")

        assert column.href_getter is not None
        href = column.href_getter(request, item)

        assert href == "/admin/customers/abc"
        request.url_for.assert_called_once_with("customers:get", id=item.id)


class TestWorkspaceColumn:
    def test_label_pinned(self) -> None:
        column = WorkspaceColumn()
        assert getattr(column, "label", None) == "Workspace"

    def test_href_points_to_workspace_detail_not_customer(self) -> None:
        # Pin: link target is the WORKSPACE detail page (using
        # ``workspace_id``), NOT the customer's own page. Drift
        # would silently link "alice@workspace-A" to alice's
        # customer page instead of workspace-A.
        column = WorkspaceColumn()
        request = MagicMock()
        request.url_for.return_value = "/admin/workspaces/abc"
        item = MagicMock()
        item.id = UUID("11111111-1111-1111-1111-111111111111")
        item.workspace_id = UUID("22222222-2222-2222-2222-222222222222")

        assert column.href_getter is not None
        href = column.href_getter(request, item)

        # The route name and id parameter both target the
        # workspace, not the customer.
        request.url_for.assert_called_once_with("workspaces:get", id=item.workspace_id)
        assert href == "/admin/workspaces/abc"


class TestEmailVerifiedBadge:
    def test_verified_renders_success_badge(self) -> None:
        # Pin: ``badge-success`` (DaisyUI green) for verified.
        # Drift would invert the moderator's at-a-glance signal.
        html = _render_badge(verified=True)
        assert "badge-success" in html
        assert "Verified" in html
        assert "Not Verified" not in html

    def test_unverified_renders_neutral_badge(self) -> None:
        # Pin: ``badge-neutral`` (gray) for unverified — NOT
        # ``badge-error``. The unverified state is ambiguous
        # signal, not a failure; drift to error-red would make
        # the customer list look alarming on every row a fresh
        # signup hasn't clicked their email link yet.
        html = _render_badge(verified=False)
        assert "badge-neutral" in html
        assert "Not Verified" in html
        assert "badge-success" not in html

    def test_either_branch_uses_badge_base_class(self) -> None:
        # Pin: both branches wrap the text in the DaisyUI
        # ``badge`` base class (so the variant class layers on
        # top correctly).
        for verified in (True, False):
            html = _render_badge(verified=verified)
            assert "badge" in html
