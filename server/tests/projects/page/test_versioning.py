"""Tests for the page versioning hook in ``rapidly.projects.page.actions``.

Pinned behaviour:

- ``_content_changed`` returns True iff at least one versioned field is
  actually changing (name / description_json / description_html).
- ``_content_changed`` ignores metadata-only edits (access, is_locked,
  parent_id, slug).
- ``_snapshot_page`` writes a row with ``version_number = max + 1``,
  capturing the *previous* (current-row) content.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from rapidly.identity.auth.models import AuthPrincipal
from rapidly.models import ProjectPage, ProjectPageAccess, User
from rapidly.projects.page import actions as page_actions


def _principal() -> AuthPrincipal[User]:
    return AuthPrincipal(
        subject=User(id=uuid4(), email="dev@example.com"),
        scopes=set(),
        session=None,
    )


def _page(
    name: str = "Original",
    description_html: str | None = "<p>v1</p>",
) -> ProjectPage:
    return ProjectPage(
        id=uuid4(),
        project_id=uuid4(),
        name=name,
        slug="original",
        description_json=None,
        description_html=description_html,
        access=ProjectPageAccess.public,
        is_locked=False,
    )


class TestContentChanged:
    def test_returns_true_when_name_changes(self) -> None:
        page = _page(name="Old")
        assert page_actions._content_changed(page, {"name": "New"}) is True

    def test_returns_true_when_html_changes(self) -> None:
        page = _page(description_html="<p>v1</p>")
        assert (
            page_actions._content_changed(page, {"description_html": "<p>v2</p>"})
            is True
        )

    def test_returns_false_when_same_value(self) -> None:
        """``model_dump(exclude_unset=True)`` keeps no-op writes; skip them."""
        page = _page(name="Same")
        assert page_actions._content_changed(page, {"name": "Same"}) is False

    def test_returns_false_for_metadata_only(self) -> None:
        page = _page()
        # access / is_locked / parent_id / slug must not trigger a version
        assert (
            page_actions._content_changed(
                page,
                {
                    "access": ProjectPageAccess.private,
                    "is_locked": True,
                    "parent_id": uuid4(),
                    "slug": "renamed",
                },
            )
            is False
        )

    def test_returns_true_with_mixed_metadata_and_content(self) -> None:
        page = _page(name="Old")
        assert (
            page_actions._content_changed(
                page,
                {"name": "New", "is_locked": True},
            )
            is True
        )


@pytest.mark.asyncio
class TestSnapshotPage:
    async def test_writes_version_with_next_number(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        principal = _principal()
        page = _page(name="Hello", description_html="<p>before</p>")
        session = MagicMock()
        # Existing max version = 3, so the new snapshot must be #4.
        session.execute = AsyncMock(
            return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=3))
        )
        captured: list[Any] = []
        session.add = lambda obj: captured.append(obj)

        await page_actions._snapshot_page(session, page, principal)

        assert len(captured) == 1
        version = captured[0]
        assert version.page_id == page.id
        assert version.version_number == 4
        assert version.name == "Hello"
        assert version.description_html == "<p>before</p>"
        assert version.author_id == principal.subject.id

    async def test_first_version_starts_at_one(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        principal = _principal()
        page = _page()
        session = MagicMock()
        session.execute = AsyncMock(
            return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None))
        )
        captured: list[Any] = []
        session.add = lambda obj: captured.append(obj)

        await page_actions._snapshot_page(session, page, principal)

        assert captured[0].version_number == 1


@pytest.mark.asyncio
class TestUpdateIntegration:
    """Integration-light: the update path calls ``_snapshot_page`` exactly
    when ``_content_changed`` returns True.
    """

    async def test_metadata_only_update_skips_snapshot(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        principal = _principal()
        page = _page()
        session = MagicMock()

        async def _ensure_member(*_a: Any, **_k: Any) -> Any:
            return MagicMock(id=page.project_id)

        async def _require_aa(*_a: Any, **_k: Any) -> None:
            return None

        snapshot_calls: list[Any] = []

        async def _snapshot(*_a: Any, **_k: Any) -> None:
            snapshot_calls.append(_a)

        monkeypatch.setattr(
            "rapidly.projects.page.actions._ensure_member", _ensure_member
        )
        monkeypatch.setattr(
            "rapidly.projects.page.actions._require_author_or_admin",
            _require_aa,
        )
        monkeypatch.setattr("rapidly.projects.page.actions._snapshot_page", _snapshot)

        from rapidly.projects.page.types import ProjectPageUpdate

        repo = MagicMock()
        repo.update = AsyncMock(return_value=page)
        repo.get_by_slug = AsyncMock(return_value=None)

        with patch(
            "rapidly.projects.page.actions.ProjectPageRepository.from_session",
            return_value=repo,
        ):
            await page_actions.update(
                session,
                principal,
                page,
                ProjectPageUpdate(is_locked=True),
            )

        assert snapshot_calls == []
        assert repo.update.await_count == 1

    async def test_content_update_writes_snapshot(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        principal = _principal()
        page = _page(name="Before")
        session = MagicMock()

        async def _ensure_member(*_a: Any, **_k: Any) -> Any:
            return MagicMock(id=page.project_id)

        async def _require_aa(*_a: Any, **_k: Any) -> None:
            return None

        snapshot_calls: list[Any] = []

        async def _snapshot(_s: Any, p: Any, _ps: Any) -> None:
            snapshot_calls.append(p)

        monkeypatch.setattr(
            "rapidly.projects.page.actions._ensure_member", _ensure_member
        )
        monkeypatch.setattr(
            "rapidly.projects.page.actions._require_author_or_admin",
            _require_aa,
        )
        monkeypatch.setattr("rapidly.projects.page.actions._snapshot_page", _snapshot)

        from rapidly.projects.page.types import ProjectPageUpdate

        repo = MagicMock()
        repo.update = AsyncMock(return_value=page)
        repo.get_by_slug = AsyncMock(return_value=None)

        with patch(
            "rapidly.projects.page.actions.ProjectPageRepository.from_session",
            return_value=repo,
        ):
            await page_actions.update(
                session,
                principal,
                page,
                ProjectPageUpdate(name="After"),
            )

        # One snapshot per content-changing update.
        assert len(snapshot_calls) == 1
        assert snapshot_calls[0] is page
