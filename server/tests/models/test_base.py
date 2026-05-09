"""Tests for base ORM model utilities."""

import pytest

from rapidly.models import User


@pytest.mark.asyncio
async def test_repr(user: User) -> None:
    assert repr(user) == f"User(id={user.id!r})"
