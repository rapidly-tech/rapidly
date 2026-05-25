"""Tests for ``rapidly.agents.workflow_version.actions``.

Schema-validation + version-numbering invariants are pinned here;
the cascade-on-workflow-delete behaviour belongs in a route /
integration test once a DB fixture exists.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from rapidly.agents.workflow_version import actions
from rapidly.agents.workflow_version.types import WorkflowVersionCreate
from rapidly.identity.auth.models import AuthPrincipal
from rapidly.models import User


def _principal() -> AuthPrincipal[User]:
    return AuthPrincipal(
        subject=User(id=uuid4(), email="dev@example.com"),
        scopes=set(),
        session=None,
    )


class TestSchemaValidation:
    def test_rejects_payload_missing_nodes_key(self) -> None:
        with pytest.raises(ValueError, match="must include nodes and edges"):
            WorkflowVersionCreate(graph_json={"edges": []})

    def test_rejects_payload_missing_edges_key(self) -> None:
        with pytest.raises(ValueError, match="must include nodes and edges"):
            WorkflowVersionCreate(graph_json={"nodes": []})

    def test_rejects_payload_with_non_list_nodes(self) -> None:
        with pytest.raises(ValueError, match="must be lists"):
            WorkflowVersionCreate(graph_json={"nodes": {}, "edges": []})

    def test_accepts_minimal_valid_payload(self) -> None:
        # Empty lists are acceptable — the editor publishes a blank
        # graph at workflow-create-time so the runtime has something
        # to target until edits land.
        v = WorkflowVersionCreate(graph_json={"nodes": [], "edges": []})
        assert v.graph_json == {"nodes": [], "edges": []}


@pytest.mark.asyncio
class TestCreate:
    async def test_assigns_next_version_number(self) -> None:
        principal = _principal()
        workflow_id = uuid4()

        captured: list[Any] = []
        repo = MagicMock()
        repo.next_version_number = AsyncMock(return_value=7)

        async def _create(obj: Any, flush: bool = False) -> Any:
            captured.append(obj)
            return obj

        repo.create = _create

        with patch(
            "rapidly.agents.workflow_version.actions.WorkflowVersionRepository.from_session",
            return_value=repo,
        ):
            await actions.create(
                MagicMock(),
                principal,
                workflow_id=workflow_id,
                data=WorkflowVersionCreate(graph_json={"nodes": [], "edges": []}),
            )

        assert captured[0].version_number == 7
        assert captured[0].workflow_id == workflow_id
        assert captured[0].created_by_id == principal.subject.id

    async def test_stores_graph_json_verbatim(self) -> None:
        principal = _principal()
        workflow_id = uuid4()

        graph = {
            "nodes": [{"id": "n1", "type": "llm", "config": {"model": "claude"}}],
            "edges": [],
        }

        captured: list[Any] = []
        repo = MagicMock()
        repo.next_version_number = AsyncMock(return_value=1)

        async def _create(obj: Any, flush: bool = False) -> Any:
            captured.append(obj)
            return obj

        repo.create = _create

        with patch(
            "rapidly.agents.workflow_version.actions.WorkflowVersionRepository.from_session",
            return_value=repo,
        ):
            await actions.create(
                MagicMock(),
                principal,
                workflow_id=workflow_id,
                data=WorkflowVersionCreate(graph_json=graph),
            )

        assert captured[0].graph_json == graph
