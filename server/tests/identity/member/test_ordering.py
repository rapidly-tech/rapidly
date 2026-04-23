"""Tests for ``rapidly/identity/member/ordering.py``."""

from __future__ import annotations

from rapidly.identity.member.ordering import MemberSortProperty


class TestMemberSortProperty:
    def test_contains_only_created_at(self) -> None:
        # Minimal sort surface — pinned so additions go through API
        # review.
        assert {e.value for e in MemberSortProperty} == {"created_at"}

    def test_is_str_enum(self) -> None:
        assert str(MemberSortProperty.created_at) == "created_at"
