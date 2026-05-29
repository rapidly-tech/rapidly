"""Unit tests for ``rapidly.agents.execution.actions``.

These test the pre-flight guards on ``start_run`` (M5.78
added the archive guard alongside the existing no-version
guard) at a unit level — they short-circuit before any
session work happens.
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from rapidly.agents.execution import actions
from rapidly.errors import NotPermitted
from rapidly.identity.auth.models import AuthPrincipal
from rapidly.models import User, Workflow


def _principal() -> AuthPrincipal[User]:
    return AuthPrincipal(
        subject=User(id=uuid4(), email="dev@example.com"),
        scopes=set(),
        session=None,
    )


@pytest.mark.asyncio
class TestStartRunArchiveGuard:
    async def test_archived_workflow_rejected(self) -> None:
        """An archived workflow can't be triggered — operator must
        unarchive first (symmetric with the user-facing 'active
        only' default on the workflows list)."""
        workflow = Workflow(
            id=uuid4(),
            workspace_id=uuid4(),
            name="retired",
            current_version_id=uuid4(),
            archived_at=datetime.now(UTC),
        )
        with pytest.raises(NotPermitted, match="archived"):
            await actions.start_run(
                MagicMock(),
                _principal(),
                workflow=workflow,
                input_data={"text": "x"},
            )

    async def test_archive_guard_runs_before_version_guard(self) -> None:
        """An archived workflow without a published version surfaces
        the archive message (the more actionable one — unarchive
        first), not the publish-version one. Ordering matters because
        otherwise operators would chase the wrong fix."""
        workflow = Workflow(
            id=uuid4(),
            workspace_id=uuid4(),
            name="retired-and-unpublished",
            current_version_id=None,
            archived_at=datetime.now(UTC),
        )
        with pytest.raises(NotPermitted, match="archived"):
            await actions.start_run(
                MagicMock(),
                _principal(),
                workflow=workflow,
                input_data={"text": "x"},
            )

    async def test_active_workflow_without_version_still_rejected(self) -> None:
        """Sanity — the pre-existing no-version guard still fires
        when archive is None."""
        workflow = Workflow(
            id=uuid4(),
            workspace_id=uuid4(),
            name="draft",
            current_version_id=None,
            archived_at=None,
        )
        with pytest.raises(NotPermitted, match="published version"):
            await actions.start_run(
                MagicMock(),
                _principal(),
                workflow=workflow,
                input_data={"text": "x"},
            )
