"""Tests for ``rapidly/platform/search/actions.py``.

Three load-bearing surfaces:

- ``_try_parse_uuid`` returns ``None`` for non-UUID input AND
  attribute-error inputs (e.g., ``None``). Drift to raise would
  500 every search query that isn't UUID-shaped.
- ``_has_shares_scope`` / ``_has_customers_scope`` evaluate to
  True when the principal carries ANY of the documented scopes:
  ``web_read``, ``web_write``, plus the resource-specific
  ``{shares,customers}_{read,write}``. Drift would let a
  customers-only API token search shares (or vice versa).
- ``search`` calls the repository with both scope flags AND the
  parsed UUID (when present), and validates each row through
  ``SearchResultTypeAdapter``. Drift to skip validation would
  let raw rows leak as a Pydantic-shaped response.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest

from rapidly.identity.auth.scope import Scope
from rapidly.platform.search.actions import (
    _has_customers_scope,
    _has_shares_scope,
    _try_parse_uuid,
    search,
)


def _make_principal(scopes: set[Scope], user_id: UUID | None = None) -> Any:
    p = MagicMock()
    p.scopes = scopes
    p.subject = MagicMock()
    p.subject.id = user_id or uuid4()
    return p


class TestTryParseUuid:
    def test_valid_uuid_returns_uuid(self) -> None:
        result = _try_parse_uuid("11111111-1111-1111-1111-111111111111")
        assert result == UUID("11111111-1111-1111-1111-111111111111")

    def test_strips_whitespace(self) -> None:
        # Pin: leading/trailing spaces from copy-paste are
        # tolerated. Drift would force admins to clean up their
        # paste before the search worked.
        result = _try_parse_uuid("  11111111-1111-1111-1111-111111111111  ")
        assert result == UUID("11111111-1111-1111-1111-111111111111")

    def test_non_uuid_returns_none(self) -> None:
        # Pin: text queries fall through to None — the caller
        # branches on this for text vs. UUID search.
        assert _try_parse_uuid("alice") is None

    def test_empty_string_returns_none(self) -> None:
        assert _try_parse_uuid("") is None

    def test_attribute_error_returns_none(self) -> None:
        # Pin: ``None.strip()`` raises AttributeError; the helper
        # swallows it. Drift would let a bug elsewhere (passing
        # a missing `?q=` param as None) crash search.
        assert _try_parse_uuid(None) is None  # type: ignore[arg-type]


class TestHasSharesScope:
    def test_shares_read_alone_grants_scope(self) -> None:
        # Pin: a shares-specific scope is enough. Drift to
        # require web_* would block API-token searches.
        principal = _make_principal({Scope.shares_read})
        assert _has_shares_scope(principal) is True

    def test_shares_write_grants_scope(self) -> None:
        principal = _make_principal({Scope.shares_write})
        assert _has_shares_scope(principal) is True

    def test_web_read_grants_scope(self) -> None:
        # Pin: dashboard-cookie auth (web_read) is in the allow-
        # list — admins shouldn't need a separate scope to use
        # the search bar.
        principal = _make_principal({Scope.web_read})
        assert _has_shares_scope(principal) is True

    def test_customers_only_does_not_grant_shares_scope(self) -> None:
        # Pin: scopes don't bleed across resources. Drift to
        # treat customers_* as also-shares would over-share the
        # API surface.
        principal = _make_principal({Scope.customers_read})
        assert _has_shares_scope(principal) is False

    def test_no_relevant_scopes_returns_false(self) -> None:
        principal = _make_principal(set())
        assert _has_shares_scope(principal) is False


class TestHasCustomersScope:
    def test_customers_read_grants_scope(self) -> None:
        principal = _make_principal({Scope.customers_read})
        assert _has_customers_scope(principal) is True

    def test_customers_write_grants_scope(self) -> None:
        principal = _make_principal({Scope.customers_write})
        assert _has_customers_scope(principal) is True

    def test_web_read_grants_scope(self) -> None:
        principal = _make_principal({Scope.web_read})
        assert _has_customers_scope(principal) is True

    def test_shares_only_does_not_grant_customers_scope(self) -> None:
        # Pin: cross-scope leak guard mirror of the shares test.
        principal = _make_principal({Scope.shares_read})
        assert _has_customers_scope(principal) is False


@pytest.mark.asyncio
class TestSearchActionWiring:
    async def test_passes_scope_flags_to_repository(self) -> None:
        # Pin: action correctly forwards both scope booleans into
        # the repository. Drift to compute one and forget the
        # other would silently drop half the results.
        principal = _make_principal({Scope.shares_read, Scope.customers_write})
        captured: dict[str, Any] = {}

        async def _fake_search(**kwargs: Any) -> list[Any]:
            captured.update(kwargs)
            return []

        with patch(
            "rapidly.platform.search.actions.SearchRepository.from_session"
        ) as mock_from_session:
            repo_mock = MagicMock()
            repo_mock.search = AsyncMock(side_effect=_fake_search)
            mock_from_session.return_value = repo_mock

            await search(
                session=MagicMock(),
                auth_subject=principal,
                workspace_id=uuid4(),
                query="alice",
            )

            assert captured["has_shares_scope"] is True
            assert captured["has_customers_scope"] is True

    async def test_uuid_query_forwards_parsed_uuid(self) -> None:
        # Pin: action parses the UUID and forwards it as
        # ``query_uuid``. Drift to forward None for valid UUID
        # inputs would force the repo into the text-search path
        # for UUID pastes.
        principal = _make_principal({Scope.web_read})
        captured: dict[str, Any] = {}

        async def _fake_search(**kwargs: Any) -> list[Any]:
            captured.update(kwargs)
            return []

        with patch(
            "rapidly.platform.search.actions.SearchRepository.from_session"
        ) as mock_from_session:
            repo_mock = MagicMock()
            repo_mock.search = AsyncMock(side_effect=_fake_search)
            mock_from_session.return_value = repo_mock

            await search(
                session=MagicMock(),
                auth_subject=principal,
                workspace_id=uuid4(),
                query="11111111-1111-1111-1111-111111111111",
            )

            assert captured["query_uuid"] == UUID(
                "11111111-1111-1111-1111-111111111111"
            )

    async def test_text_query_passes_none_query_uuid(self) -> None:
        # Pin: non-UUID input → query_uuid=None.
        principal = _make_principal({Scope.web_read})
        captured: dict[str, Any] = {}

        async def _fake_search(**kwargs: Any) -> list[Any]:
            captured.update(kwargs)
            return []

        with patch(
            "rapidly.platform.search.actions.SearchRepository.from_session"
        ) as mock_from_session:
            repo_mock = MagicMock()
            repo_mock.search = AsyncMock(side_effect=_fake_search)
            mock_from_session.return_value = repo_mock

            await search(
                session=MagicMock(),
                auth_subject=principal,
                workspace_id=uuid4(),
                query="alice",
            )

            assert captured["query_uuid"] is None

    async def test_passes_user_id_from_principal(self) -> None:
        # Pin: action uses the principal's subject id as the
        # search-time user_id (which the repo uses for the
        # privacy-guard membership check). Drift to forward a
        # different id would let an admin-impersonated session
        # see the WRONG user's authorised workspaces in search
        # results.
        user_id = uuid4()
        principal = _make_principal({Scope.web_read}, user_id=user_id)
        captured: dict[str, Any] = {}

        async def _fake_search(**kwargs: Any) -> list[Any]:
            captured.update(kwargs)
            return []

        with patch(
            "rapidly.platform.search.actions.SearchRepository.from_session"
        ) as mock_from_session:
            repo_mock = MagicMock()
            repo_mock.search = AsyncMock(side_effect=_fake_search)
            mock_from_session.return_value = repo_mock

            await search(
                session=MagicMock(),
                auth_subject=principal,
                workspace_id=uuid4(),
                query="x",
            )

            assert captured["user_id"] == user_id
