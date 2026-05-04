"""Tests for ``rapidly/platform/workspace_access_token/actions.py``.

Five load-bearing surfaces:

- ``TOKEN_PREFIX`` is pinned to ``"rapidly_oat_"`` — drift would
  invalidate every existing OAT in production AND break secret-
  scanning regex patterns that match this prefix to detect
  leaked tokens.
- ``create`` joins scope literals with a SPACE (OAuth 2.0 RFC
  6749 token format). Drift to comma / pipe would break every
  parser that splits scope strings on whitespace.
- ``create`` sets ``expires_at = now() + expires_in`` when the
  caller supplies a ``expires_in`` timedelta; sets ``None``
  (never expires) when omitted.
- ``get_by_token`` HASHES the supplied raw token before lookup
  via ``get_token_hash`` with the configured secret. Drift to
  compare raw token to the stored hash would break every
  authentication call (no token would match its own DB row).
- ``update`` joins scopes with SPACE (mirror of create);
  ``exclude_unset=True`` so partial updates don't clobber
  unspecified fields. Drift would let "edit comment" reset the
  scope list to empty.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from freezegun import freeze_time

from rapidly.platform.workspace_access_token.actions import (
    TOKEN_PREFIX,
    create,
    delete,
    get_by_token,
    update,
)


class TestTokenPrefix:
    def test_pinned_to_rapidly_oat(self) -> None:
        # Pin: drift would invalidate every existing OAT in
        # production AND break secret-scanning regex patterns
        # that match this prefix to detect leaked tokens.
        assert TOKEN_PREFIX == "rapidly_oat_"


@pytest.mark.asyncio
class TestGetByToken:
    async def test_hashes_raw_token_before_lookup(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Pin: ``get_token_hash`` is applied. Drift to compare
        # raw token to stored hash would break EVERY auth call
        # — the stored DB row is the hash, not the bearer.
        captured: dict[str, Any] = {}

        def _fake_hash(token: str, *, secret: str) -> str:
            captured["raw"] = token
            captured["secret"] = secret
            return f"hashed:{token}"

        monkeypatch.setattr(
            "rapidly.platform.workspace_access_token.actions.get_token_hash",
            _fake_hash,
        )

        repo = MagicMock()
        repo.get_by_token_hash = AsyncMock(return_value=None)
        monkeypatch.setattr(
            "rapidly.platform.workspace_access_token.actions"
            ".WorkspaceAccessTokenRepository.from_session",
            MagicMock(return_value=repo),
        )

        await get_by_token(MagicMock(), "rapidly_oat_xyz")

        # The hash function ran with the caller's raw token.
        assert captured["raw"] == "rapidly_oat_xyz"
        # And the repo lookup used the hashed value.
        repo.get_by_token_hash.assert_called_once_with(
            "hashed:rapidly_oat_xyz", expired=False
        )

    async def test_expired_flag_forwarded(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Pin: admin/audit can opt into expired tokens via the
        # ``expired`` flag — drift to drop would 404 admin token
        # detail pages.
        monkeypatch.setattr(
            "rapidly.platform.workspace_access_token.actions.get_token_hash",
            lambda token, *, secret: "h",
        )
        repo = MagicMock()
        repo.get_by_token_hash = AsyncMock(return_value=None)
        monkeypatch.setattr(
            "rapidly.platform.workspace_access_token.actions"
            ".WorkspaceAccessTokenRepository.from_session",
            MagicMock(return_value=repo),
        )

        await get_by_token(MagicMock(), "rapidly_oat_xyz", expired=True)

        repo.get_by_token_hash.assert_called_once_with("h", expired=True)


@pytest.mark.asyncio
class TestCreateScopeJoinAndExpiry:
    async def test_scopes_joined_with_space(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Pin: OAuth 2.0 scope strings are space-separated (RFC
        # 6749). Drift to comma / pipe would break every parser
        # that splits on whitespace.
        captured: dict[str, Any] = {}

        async def _create(obj: object, flush: bool = False) -> object:
            captured["obj"] = obj
            return obj

        repo = MagicMock()
        repo.create = AsyncMock(side_effect=_create)
        monkeypatch.setattr(
            "rapidly.platform.workspace_access_token.actions"
            ".WorkspaceAccessTokenRepository.from_session",
            MagicMock(return_value=repo),
        )

        async def _resolve_workspace(*args: Any, **kwargs: Any) -> Any:
            return MagicMock()

        monkeypatch.setattr(
            "rapidly.platform.workspace_access_token.actions.get_payload_workspace",
            _resolve_workspace,
        )
        monkeypatch.setattr(
            "rapidly.platform.workspace_access_token.actions.generate_token_hash_pair",
            lambda secret, prefix: ("rawtoken", "hashtoken"),
        )

        body = MagicMock()
        body.model_dump.return_value = {"comment": "ci"}
        body.scopes = ["shares:read", "customers:read"]
        body.expires_in = None

        await create(MagicMock(), MagicMock(), body)

        # The persisted obj's scope is space-joined.
        assert captured["obj"].scope == "shares:read customers:read"

    async def test_expires_at_is_now_plus_expires_in(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Pin: ``expires_at = now_utc() + expires_in``. Drift to
        # the wrong epoch base would expire tokens at the wrong
        # time.
        captured: dict[str, Any] = {}

        async def _create(obj: object, flush: bool = False) -> object:
            captured["obj"] = obj
            return obj

        repo = MagicMock()
        repo.create = AsyncMock(side_effect=_create)
        monkeypatch.setattr(
            "rapidly.platform.workspace_access_token.actions"
            ".WorkspaceAccessTokenRepository.from_session",
            MagicMock(return_value=repo),
        )

        async def _resolve_workspace(*args: Any, **kwargs: Any) -> Any:
            return MagicMock()

        monkeypatch.setattr(
            "rapidly.platform.workspace_access_token.actions.get_payload_workspace",
            _resolve_workspace,
        )
        monkeypatch.setattr(
            "rapidly.platform.workspace_access_token.actions.generate_token_hash_pair",
            lambda secret, prefix: ("rawtoken", "hashtoken"),
        )

        body = MagicMock()
        body.model_dump.return_value = {"comment": "ci"}
        body.scopes = ["shares:read"]
        body.expires_in = timedelta(days=30)

        with freeze_time(datetime(2026, 4, 25, 12, 0, tzinfo=UTC)):
            await create(MagicMock(), MagicMock(), body)

        assert captured["obj"].expires_at == datetime(2026, 5, 25, 12, 0, tzinfo=UTC)

    async def test_no_expires_in_means_never_expires(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Pin: omitted ``expires_in`` → ``expires_at=None``
        # (never expires; standard for long-lived service
        # tokens). Drift to default-30d would silently expire
        # production integrations.
        captured: dict[str, Any] = {}

        async def _create(obj: object, flush: bool = False) -> object:
            captured["obj"] = obj
            return obj

        repo = MagicMock()
        repo.create = AsyncMock(side_effect=_create)
        monkeypatch.setattr(
            "rapidly.platform.workspace_access_token.actions"
            ".WorkspaceAccessTokenRepository.from_session",
            MagicMock(return_value=repo),
        )

        async def _resolve_workspace(*args: Any, **kwargs: Any) -> Any:
            return MagicMock()

        monkeypatch.setattr(
            "rapidly.platform.workspace_access_token.actions.get_payload_workspace",
            _resolve_workspace,
        )
        monkeypatch.setattr(
            "rapidly.platform.workspace_access_token.actions.generate_token_hash_pair",
            lambda secret, prefix: ("rawtoken", "hashtoken"),
        )

        body = MagicMock()
        body.model_dump.return_value = {"comment": "ci"}
        body.scopes = ["shares:read"]
        body.expires_in = None

        await create(MagicMock(), MagicMock(), body)

        assert captured["obj"].expires_at is None

    async def test_returns_token_pair(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # Pin: the action returns ``(model, raw_token)`` so the
        # API handler can show the raw token EXACTLY ONCE to the
        # creator. Drift to drop the raw value would break the
        # token-creation UX.
        repo = MagicMock()
        repo.create = AsyncMock(side_effect=lambda obj, flush=False: obj)
        monkeypatch.setattr(
            "rapidly.platform.workspace_access_token.actions"
            ".WorkspaceAccessTokenRepository.from_session",
            MagicMock(return_value=repo),
        )

        async def _resolve_workspace(*args: Any, **kwargs: Any) -> Any:
            return MagicMock()

        monkeypatch.setattr(
            "rapidly.platform.workspace_access_token.actions.get_payload_workspace",
            _resolve_workspace,
        )
        monkeypatch.setattr(
            "rapidly.platform.workspace_access_token.actions.generate_token_hash_pair",
            lambda secret, prefix: ("rawtoken_xyz", "hashtoken_xyz"),
        )

        body = MagicMock()
        body.model_dump.return_value = {"comment": "ci"}
        body.scopes = ["shares:read"]
        body.expires_in = None

        _, raw = await create(MagicMock(), MagicMock(), body)

        assert raw == "rawtoken_xyz"


@pytest.mark.asyncio
class TestUpdate:
    async def test_partial_update_excludes_unset_fields(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Pin: ``exclude_unset=True`` so editing the comment
        # alone doesn't clobber the scope list. Drift to set-
        # all would reset every unspecified field to default.
        captured: dict[str, Any] = {}

        async def _update(obj: Any, update_dict: dict[str, Any]) -> Any:
            captured["update_dict"] = update_dict
            return obj

        repo = MagicMock()
        repo.update = AsyncMock(side_effect=_update)
        monkeypatch.setattr(
            "rapidly.platform.workspace_access_token.actions"
            ".WorkspaceAccessTokenRepository.from_session",
            MagicMock(return_value=repo),
        )

        # Caller only sets `comment`, scopes left unset.
        body = MagicMock()
        body.model_dump.return_value = {"comment": "renamed"}
        body.scopes = None

        await update(MagicMock(), MagicMock(), body)

        # Update dict carries comment but NOT a scope override.
        assert captured["update_dict"] == {"comment": "renamed"}
        assert "scope" not in captured["update_dict"]

    async def test_scopes_update_joined_with_space(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Pin: scope-update path uses the same space-join as
        # create.
        captured: dict[str, Any] = {}

        async def _update(obj: Any, update_dict: dict[str, Any]) -> Any:
            captured["update_dict"] = update_dict
            return obj

        repo = MagicMock()
        repo.update = AsyncMock(side_effect=_update)
        monkeypatch.setattr(
            "rapidly.platform.workspace_access_token.actions"
            ".WorkspaceAccessTokenRepository.from_session",
            MagicMock(return_value=repo),
        )

        body = MagicMock()
        body.model_dump.return_value = {}
        body.scopes = ["shares:read", "customers:read"]

        await update(MagicMock(), MagicMock(), body)

        assert captured["update_dict"]["scope"] == "shares:read customers:read"


@pytest.mark.asyncio
class TestDelete:
    async def test_calls_soft_delete_on_repository(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Pin: tokens go through SOFT delete so audit-log rows
        # referencing the token still resolve. Drift to hard
        # delete would orphan audit context.
        repo = MagicMock()
        repo.soft_delete = AsyncMock()
        monkeypatch.setattr(
            "rapidly.platform.workspace_access_token.actions"
            ".WorkspaceAccessTokenRepository.from_session",
            MagicMock(return_value=repo),
        )

        token = MagicMock()
        await delete(MagicMock(), token)

        repo.soft_delete.assert_called_once_with(token)
