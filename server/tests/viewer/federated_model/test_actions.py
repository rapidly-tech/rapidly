"""Tests for ``rapidly.viewer.federated_model.actions``.

Action-level only — route tests + integration with the actual
parse worker land in M3.1b.

Invariants pinned:
- ``create`` writes a row in ``status='uploaded'`` (the parse
  worker, not this call, flips it to 'parsing'/'ready')
- ``create`` preserves the provided source_file_id verbatim (the
  frontend already did the multipart upload via catalog/file)
"""

from __future__ import annotations

from datetime import UTC
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from rapidly.identity.auth.models import AuthPrincipal
from rapidly.models import FederatedModel, ModelStatus, User
from rapidly.viewer.federated_model import actions
from rapidly.viewer.federated_model.types import FederatedModelCreate


def _principal() -> AuthPrincipal[User]:
    return AuthPrincipal(
        subject=User(id=uuid4(), email="dev@example.com"),
        scopes=set(),
        session=None,
    )


@pytest.mark.asyncio
class TestCreate:
    async def test_starts_in_uploaded_status(self) -> None:
        principal = _principal()
        project_id = uuid4()
        source_file_id = uuid4()

        captured: list[Any] = []
        repo = MagicMock()

        async def _create(obj: Any, flush: bool = False) -> Any:
            captured.append(obj)
            return obj

        repo.create = _create

        with patch(
            "rapidly.viewer.federated_model.actions.FederatedModelRepository.from_session",
            return_value=repo,
        ):
            await actions.create(
                MagicMock(),
                principal,
                FederatedModelCreate(
                    project_id=project_id,
                    name="arch.ifc",
                    source_file_id=source_file_id,
                ),
            )

        assert captured[0].status == ModelStatus.uploaded
        assert captured[0].project_id == project_id
        assert captured[0].source_file_id == source_file_id
        assert captured[0].name == "arch.ifc"
        # Worker fills these in later — not the action's job.
        assert captured[0].xkt_file_id is None
        assert captured[0].units is None
        assert captured[0].element_count is None
        assert captured[0].bbox is None


@pytest.mark.asyncio
class TestGetXktDownloadUrl:
    async def test_raises_when_xkt_file_id_not_set(self) -> None:
        # status='uploaded' / 'parsing' / 'failed' all imply
        # xkt_file_id is None — request the URL on any of those and
        # we should 404 (handled at the route level via the
        # ResourceNotFound exception handler).
        from datetime import datetime
        from unittest.mock import AsyncMock, MagicMock

        from rapidly.errors import ResourceNotFound
        from rapidly.models import FederatedModel, ModelStatus
        from rapidly.viewer.federated_model import actions

        model = MagicMock(spec=FederatedModel)
        model.xkt_file_id = None
        model.status = ModelStatus.parsing

        with pytest.raises(ResourceNotFound, match="not in ready"):
            await actions.get_xkt_download_url(AsyncMock(), model)

        # datetime unused-import elimination
        _ = datetime

    async def test_returns_url_and_expiry_for_ready_model(self) -> None:
        # Happy path: status='ready' + xkt_file_id set → delegate to
        # ``catalog/file.actions.generate_download_url`` and forward.
        from datetime import datetime
        from unittest.mock import AsyncMock, MagicMock, patch

        from rapidly.models import FederatedModel, File
        from rapidly.viewer.federated_model import actions

        model = MagicMock(spec=FederatedModel)
        model.xkt_file_id = uuid4()

        file_row = MagicMock(spec=File)

        session = MagicMock()
        session.execute = AsyncMock(
            return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=file_row))
        )

        fake_url = "https://s3.example/signed/xkt"
        fake_expiry = datetime(2026, 12, 31, tzinfo=UTC)

        with patch(
            "rapidly.viewer.federated_model.actions.file_actions.generate_download_url",
            return_value=(fake_url, fake_expiry),
        ):
            url, expires_at = await actions.get_xkt_download_url(session, model)

        assert url == fake_url
        assert expires_at == fake_expiry


@pytest.mark.asyncio
class TestDelete:
    async def test_soft_deletes_the_row(self) -> None:
        principal = _principal()
        record = FederatedModel(
            id=uuid4(),
            project_id=uuid4(),
            name="x",
            source_file_id=uuid4(),
            status=ModelStatus.uploaded,
        )

        repo = MagicMock()
        repo.soft_delete = AsyncMock()

        with patch(
            "rapidly.viewer.federated_model.actions.FederatedModelRepository.from_session",
            return_value=repo,
        ):
            await actions.delete(MagicMock(), principal, record)

        repo.soft_delete.assert_awaited_once_with(record)
