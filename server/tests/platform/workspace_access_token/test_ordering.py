"""Tests for ``rapidly/platform/workspace_access_token/ordering.py``."""

from __future__ import annotations

from rapidly.platform.workspace_access_token.ordering import (
    WorkspaceAccessTokenSortProperty,
)


class TestWorkspaceAccessTokenSortProperty:
    def test_exposes_documented_columns(self) -> None:
        assert {e.value for e in WorkspaceAccessTokenSortProperty} == {
            "created_at",
            "comment",
            "last_used_at",
            "workspace_id",
        }

    def test_is_str_enum(self) -> None:
        assert str(WorkspaceAccessTokenSortProperty.last_used_at) == "last_used_at"
