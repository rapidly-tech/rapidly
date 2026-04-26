"""Tests for ``rapidly/core/queries/base.py``.

Generic Repository + soft-delete + sortable mixins. Five
load-bearing surfaces:

- ``Page`` is a frozen + slotted dataclass — drift to mutable
  would let one request silently mutate another's results, and
  drift to non-slotted would balloon memory on large list
  responses.
- ``Repository.create / update / delete`` honour the ``flush``
  flag: opt-in flush, NOT default. Drift to default-flush would
  let intermediate state become visible across the workspace's
  transaction.
- ``Repository.update`` calls ``flag_modified`` for each updated
  attribute so JSONB / mutable-dict columns get persisted. Drift
  would silently lose JSONB updates (the ORM treats them as
  unchanged).
- ``SoftDeleteMixin.get_base_statement(include_deleted=False)``
  filters by ``deleted_at IS NULL`` (default); ``include_deleted=
  True`` skips the filter so admin paths can recover deleted
  rows. Drift to default include-deleted would leak deleted
  rows into every list response.
- ``SortableMixin.apply_sorting`` wraps each sorting criterion
  in ``desc`` (when descending) or ``asc`` and ``order_by``s the
  combined clause. ``get_sorting_clause`` raises
  ``NotImplementedError`` so subclasses MUST override it (drift
  to a default implementation would silently sort every
  property by id).
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from rapidly.core.queries.base import (
    Page,
    Repository,
    SoftDeleteMixin,
    SortableMixin,
)


class TestPageDataclass:
    def test_is_frozen(self) -> None:
        # Pin: ``frozen=True`` so request handlers can't mutate
        # results from a parallel request via shared reference.
        from dataclasses import FrozenInstanceError

        page: Page[int] = Page(items=[1, 2], total=2)
        with pytest.raises(FrozenInstanceError):
            page.total = 99  # type: ignore[misc]

    def test_is_slotted(self) -> None:
        # Pin: ``slots=True`` saves memory on large list
        # endpoints (one __dict__ per Page would balloon
        # memory in a 100-page list response).
        page: Page[int] = Page(items=[1], total=1)
        assert not hasattr(page, "__dict__")

    def test_carries_items_and_total(self) -> None:
        page: Page[str] = Page(items=["a", "b"], total=42)
        assert list(page.items) == ["a", "b"]
        assert page.total == 42


class _FakeModel:
    """Stand-in for a SQLAlchemy mapped class."""

    deleted_at: Any = None

    def __init__(self) -> None:
        self.id = "x"


def _make_repo() -> tuple[Repository[_FakeModel], MagicMock]:
    """Build a repository whose session is a mock with async write methods."""
    session = MagicMock()
    session.add = MagicMock()
    session.flush = AsyncMock()
    session.delete = AsyncMock()
    session.execute = AsyncMock()

    class _Repo(Repository[_FakeModel]):
        model = _FakeModel

    return _Repo(session), session


@pytest.mark.asyncio
class TestRepositoryCreate:
    async def test_default_no_flush(self) -> None:
        # Pin: ``flush=False`` is the DEFAULT. Drift to default
        # flush would let intermediate state become visible to
        # SQL-level read-after-write checks before the request's
        # transaction has committed.
        repo, session = _make_repo()
        obj = _FakeModel()
        result = await repo.create(obj)
        assert result is obj
        session.add.assert_called_once_with(obj)
        session.flush.assert_not_awaited()

    async def test_flush_true_invokes_session_flush(self) -> None:
        # Pin: opt-in flush is honoured (callers that NEED an id
        # before commit, e.g., to dispatch a worker task with
        # the new row's UUID).
        repo, session = _make_repo()
        obj = _FakeModel()
        await repo.create(obj, flush=True)
        session.flush.assert_awaited_once()


@pytest.mark.asyncio
class TestRepositoryUpdate:
    async def test_applies_update_dict_attrs(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Pin: every key in ``update_dict`` is set as an attribute
        # AND ``flag_modified`` is called so JSONB / mutable-dict
        # columns are persisted.
        from rapidly.core.queries import base as M

        captured_flags: list[tuple[Any, str]] = []
        monkeypatch.setattr(
            M,
            "flag_modified",
            lambda obj, attr: captured_flags.append((obj, attr)),
        )

        repo, _ = _make_repo()
        obj = _FakeModel()
        await repo.update(obj, update_dict={"name": "Alice", "email": "a@b.com"})

        assert obj.name == "Alice"  # type: ignore[attr-defined]
        assert obj.email == "a@b.com"  # type: ignore[attr-defined]
        # flag_modified called for each updated attribute.
        assert len(captured_flags) == 2

    async def test_swallows_keyerror_on_untracked_attr(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Pin: ``flag_modified`` raises KeyError on attributes the
        # ORM isn't tracking. The update path catches and continues
        # — defensive against ad-hoc kwargs that aren't real
        # columns (e.g., a typed-dict field passed through).
        from rapidly.core.queries import base as M

        def boom(obj: Any, attr: str) -> None:
            raise KeyError(attr)

        monkeypatch.setattr(M, "flag_modified", boom)

        repo, _ = _make_repo()
        obj = _FakeModel()
        # Should NOT raise.
        await repo.update(obj, update_dict={"untracked_field": 42})
        assert obj.untracked_field == 42  # type: ignore[attr-defined]

    async def test_no_update_dict_just_adds(self) -> None:
        # Pin: omitting update_dict skips the per-attr loop and
        # just adds the (already-mutated) object. Used by callers
        # that did the mutation themselves.
        repo, session = _make_repo()
        obj = _FakeModel()
        await repo.update(obj)
        session.add.assert_called_once_with(obj)


@pytest.mark.asyncio
class TestRepositoryDelete:
    async def test_default_no_flush(self) -> None:
        repo, session = _make_repo()
        obj = _FakeModel()
        await repo.delete(obj)
        session.delete.assert_awaited_once_with(obj)
        session.flush.assert_not_awaited()

    async def test_flush_true_invokes_flush(self) -> None:
        repo, session = _make_repo()
        obj = _FakeModel()
        await repo.delete(obj, flush=True)
        session.flush.assert_awaited_once()


class TestRepositoryFromSession:
    def test_from_session_constructs_repo_with_session(self) -> None:
        # Pin: the ``from_session`` classmethod is the documented
        # construction path. Drift to private __init__ access
        # would break every action that uses it.
        sess = MagicMock()

        class _Repo(Repository[_FakeModel]):
            model = _FakeModel

        repo = _Repo.from_session(sess)
        assert isinstance(repo, _Repo)
        assert repo.session is sess


class TestSoftDeleteMixin:
    def test_default_excludes_deleted(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # Pin: default behaviour adds a ``deleted_at IS NULL``
        # filter. Drift to default include-deleted would leak
        # soft-deleted rows into every list response.
        deleted_col = MagicMock()
        sentinel_filter = "DELETED_AT_IS_NULL"
        deleted_col.is_ = MagicMock(return_value=sentinel_filter)

        class _Model:
            deleted_at = deleted_col

        # Stub super().get_base_statement() so we don't drag in
        # SQLAlchemy's Select coercion.
        base_stmt = MagicMock()
        base_stmt.where = MagicMock(return_value="WHERE_APPLIED")
        monkeypatch.setattr(Repository, "get_base_statement", lambda self_: base_stmt)

        class _Repo(SoftDeleteMixin[_Model], Repository[_Model]):
            model = _Model

        repo = _Repo(session=MagicMock())
        stmt = repo.get_base_statement()
        # ``deleted_at.is_(None)`` was called and passed to ``.where``.
        deleted_col.is_.assert_called_once_with(None)
        base_stmt.where.assert_called_once_with(sentinel_filter)
        assert stmt == "WHERE_APPLIED"  # type: ignore[comparison-overlap]

    def test_include_deleted_skips_filter(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Pin: ``include_deleted=True`` returns the base statement
        # without the deleted_at filter. Used by admin recovery
        # paths.
        deleted_col = MagicMock()
        deleted_col.is_ = MagicMock(return_value="X")

        class _Model:
            deleted_at = deleted_col

        base_stmt = MagicMock()
        base_stmt.where = MagicMock(return_value="WHERE_APPLIED")
        monkeypatch.setattr(Repository, "get_base_statement", lambda self_: base_stmt)

        class _Repo(SoftDeleteMixin[_Model], Repository[_Model]):
            model = _Model

        repo = _Repo(session=MagicMock())
        stmt = repo.get_base_statement(include_deleted=True)
        # When include_deleted is True, ``is_`` is NOT called and
        # ``.where`` is NOT applied.
        deleted_col.is_.assert_not_called()
        base_stmt.where.assert_not_called()
        # Statement is the unfiltered base.
        assert stmt is base_stmt

    @pytest.mark.asyncio
    async def test_soft_delete_sets_deleted_at_via_update(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Pin: soft_delete delegates to update() with
        # ``{"deleted_at": now_utc()}``. Drift to direct
        # session.delete would HARD-delete instead of soft.
        from rapidly.core.queries import base as M

        class _Model:
            deleted_at: Any = None

        class _Repo(SoftDeleteMixin[_Model], Repository[_Model]):
            model = _Model

        captured: dict[str, Any] = {}

        async def fake_update(self_, object, *, update_dict=None, flush=False):  # type: ignore[no-untyped-def]
            captured["update_dict"] = update_dict
            captured["flush"] = flush
            return object

        monkeypatch.setattr(Repository, "update", fake_update)

        from datetime import UTC, datetime

        sentinel = datetime(2026, 1, 1, tzinfo=UTC)
        monkeypatch.setattr(M, "now_utc", lambda: sentinel)

        repo = _Repo(session=MagicMock())
        obj = _Model()
        await repo.soft_delete(obj, flush=True)

        assert captured["update_dict"] == {"deleted_at": sentinel}
        assert captured["flush"] is True


class TestSortableMixin:
    def test_get_sorting_clause_raises_not_implemented(self) -> None:
        # Pin: subclasses MUST override. Drift to a default
        # ``return self.model.id`` would silently sort every
        # property by id and quietly break dashboard sorting.
        class _Repo(SortableMixin[_FakeModel, Any]):
            pass

        with pytest.raises(NotImplementedError):
            _Repo().get_sorting_clause(MagicMock())

    def test_apply_sorting_wraps_clauses_in_asc_or_desc(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Pin: ascending criteria use ``asc``, descending use
        # ``desc``. Drift would silently reverse customer-facing
        # list pages.
        from rapidly.core.queries import base as M

        asc_calls: list[Any] = []
        desc_calls: list[Any] = []

        def fake_asc(col: Any) -> Any:
            asc_calls.append(col)
            return ("asc", col)

        def fake_desc(col: Any) -> Any:
            desc_calls.append(col)
            return ("desc", col)

        monkeypatch.setattr(M, "asc", fake_asc)
        monkeypatch.setattr(M, "desc", fake_desc)

        class _Repo(SortableMixin[_FakeModel, Any]):
            def get_sorting_clause(self, property: Any) -> Any:
                return f"col-{property}"

        order_by_args: list[Any] = []

        class _Stmt:
            def order_by(self, *args: Any) -> Any:
                order_by_args.extend(args)
                return self

        repo = _Repo()
        stmt = _Stmt()
        result = repo.apply_sorting(
            stmt,  # type: ignore[arg-type]
            sorting=[
                ("name", False),  # asc
                ("created_at", True),  # desc
            ],
        )
        # Pin: chained order_by (returns same statement).
        assert result is stmt  # type: ignore[comparison-overlap]
        # Pin: asc applied to the False-descending criterion;
        # desc applied to the True-descending criterion.
        assert asc_calls == ["col-name"]
        assert desc_calls == ["col-created_at"]
        # Both clauses passed to order_by.
        assert len(order_by_args) == 2
