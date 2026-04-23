"""Tests for ``rapidly/platform/user/ordering.py``."""

from __future__ import annotations

from rapidly.platform.user.ordering import UserSortProperty


class TestUserSortProperty:
    def test_exposes_email_and_created_at(self) -> None:
        assert {e.value for e in UserSortProperty} == {"email", "created_at"}

    def test_is_str_enum(self) -> None:
        assert str(UserSortProperty.email) == "email"
