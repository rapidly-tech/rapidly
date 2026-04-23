"""Tests for ``rapidly/platform/workspace/ordering.py``."""

from __future__ import annotations

from rapidly.platform.workspace.ordering import WorkspaceSortProperty


class TestWorkspaceSortProperty:
    def test_exposes_documented_columns(self) -> None:
        assert {e.value for e in WorkspaceSortProperty} == {
            "created_at",
            "slug",
            "name",
            "next_review_threshold",
            "days_in_status",
        }

    def test_workspace_name_attribute_alias(self) -> None:
        # Same StrEnum reserved-word workaround as CustomerSortProperty.
        assert WorkspaceSortProperty.workspace_name.value == "name"

    def test_is_str_enum(self) -> None:
        assert str(WorkspaceSortProperty.slug) == "slug"
