"""Tests for ``rapidly/catalog/custom_field/queries.py``.

Five load-bearing surfaces:

- ``get_readable_statement`` JOINs the workspace + applies
  ``contains_eager`` (drift to lazy-load would N+1 every list
  page) AND filters out soft-deleted rows.
- ``get_readable_statement`` enforces tenant scope: USER →
  workspaces with active membership; WORKSPACE → own workspace
  only.
- ``apply_list_filters`` 2-column ILIKE search across NAME +
  SLUG with ``escape_like`` applied. Drift to drop ``escape_like``
  would let a typed ``%`` flood the field list.
- ``apply_list_filters`` ``type`` filter uses ``IN`` for multi-
  value (caller passes the documented type set).
- ``delete_attachments`` iterates EVERY model in
  ``attached_custom_fields_models`` and DELETEs scoped to the
  given ``custom_field_id``. Drift to drop the WHERE on any one
  table would mass-delete every attachment row.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from rapidly.catalog.custom_field import attachment as attachment_mod
from rapidly.catalog.custom_field.queries import CustomFieldRepository
from rapidly.models.custom_field import CustomFieldType


def _compile(stmt: object) -> str:
    return str(stmt.compile(compile_kwargs={"literal_binds": True}))  # type: ignore[attr-defined]


@pytest.mark.asyncio
class TestGetReadableStatement:
    async def test_joins_workspace_with_eager_load(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Pin: every read joins workspaces with contains_eager —
        # drift to lazy-load would N+1 every list page render.
        repo = CustomFieldRepository(session=MagicMock())
        principal = MagicMock()
        principal.subject = MagicMock()
        principal.subject.id = uuid4()

        monkeypatch.setattr(
            "rapidly.catalog.custom_field.queries.is_user_principal",
            lambda p: True,
        )
        monkeypatch.setattr(
            "rapidly.catalog.custom_field.queries.is_workspace_principal",
            lambda p: False,
        )

        stmt = repo.get_readable_statement(principal)
        sql = _compile(stmt).lower()
        assert "join workspaces" in sql

    async def test_filters_soft_deleted_rows(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Pin: ``deleted_at IS NULL`` on the custom_fields row.
        repo = CustomFieldRepository(session=MagicMock())
        principal = MagicMock()
        principal.subject = MagicMock()
        principal.subject.id = uuid4()

        monkeypatch.setattr(
            "rapidly.catalog.custom_field.queries.is_user_principal",
            lambda p: True,
        )
        monkeypatch.setattr(
            "rapidly.catalog.custom_field.queries.is_workspace_principal",
            lambda p: False,
        )

        stmt = repo.get_readable_statement(principal)
        sql = _compile(stmt).lower()
        assert "custom_fields.deleted_at is null" in sql

    async def test_user_principal_filters_by_membership(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        repo = CustomFieldRepository(session=MagicMock())
        principal = MagicMock()
        principal.subject = MagicMock()
        principal.subject.id = uuid4()

        monkeypatch.setattr(
            "rapidly.catalog.custom_field.queries.is_user_principal",
            lambda p: True,
        )
        monkeypatch.setattr(
            "rapidly.catalog.custom_field.queries.is_workspace_principal",
            lambda p: False,
        )

        stmt = repo.get_readable_statement(principal)
        sql = _compile(stmt).lower()
        assert "workspace_memberships.workspace_id" in sql
        assert "workspace_memberships.user_id" in sql
        assert "workspace_memberships.deleted_at is null" in sql

    async def test_workspace_principal_filters_to_own_workspace_id(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        repo = CustomFieldRepository(session=MagicMock())
        target = uuid4()
        principal = MagicMock()
        principal.subject = MagicMock()
        principal.subject.id = target

        monkeypatch.setattr(
            "rapidly.catalog.custom_field.queries.is_user_principal",
            lambda p: False,
        )
        monkeypatch.setattr(
            "rapidly.catalog.custom_field.queries.is_workspace_principal",
            lambda p: True,
        )

        stmt = repo.get_readable_statement(principal)
        sql = _compile(stmt).replace("-", "")
        assert target.hex in sql


class TestApplyListFiltersTextSearch:
    def test_query_searches_name_AND_slug(self) -> None:
        # Pin: 2-column ILIKE search.
        repo = CustomFieldRepository(session=MagicMock())
        from sqlalchemy import select as sa_select

        from rapidly.models import CustomField

        stmt = sa_select(CustomField)
        stmt = repo.apply_list_filters(stmt, query="invoice")
        sql = _compile(stmt).lower()
        assert "custom_fields.name" in sql
        assert "custom_fields.slug" in sql
        assert " or " in sql

    def test_escape_like_applied(self) -> None:
        # Pin: escape_like prevents user-supplied ``%`` from
        # flooding the field list.
        repo = CustomFieldRepository(session=MagicMock())
        from sqlalchemy import select as sa_select

        from rapidly.models import CustomField

        stmt = sa_select(CustomField)
        stmt = repo.apply_list_filters(stmt, query="50%off")
        sql = _compile(stmt)
        assert r"50\%off" in sql

    def test_type_filter_uses_in_clause(self) -> None:
        # Pin: ``IN`` for multi-value type filtering.
        repo = CustomFieldRepository(session=MagicMock())
        from sqlalchemy import select as sa_select

        from rapidly.models import CustomField

        stmt = sa_select(CustomField)
        stmt = repo.apply_list_filters(
            stmt, type=[CustomFieldType.text, CustomFieldType.number]
        )
        sql = _compile(stmt).lower()
        assert "custom_fields.type in" in sql


@pytest.mark.asyncio
class TestDeleteAttachments:
    async def test_iterates_every_attachment_model(self) -> None:
        # Pin: ``delete_attachments`` cascades through EVERY
        # registered attachment model. Drift to skip a model
        # would orphan rows that point at the deleted custom
        # field (FK violation later).
        repo = CustomFieldRepository(session=MagicMock())
        captured: list[Any] = []

        async def _exec(stmt: object) -> Any:
            captured.append(stmt)
            return MagicMock()

        repo.session.execute = AsyncMock(side_effect=_exec)  # type: ignore[method-assign]

        target = uuid4()
        await repo.delete_attachments(target)

        # One DELETE per registered model.
        assert len(captured) == len(attachment_mod.attached_custom_fields_models)

    async def test_each_delete_scoped_to_custom_field_id(self) -> None:
        # Pin: each DELETE narrows by ``custom_field_id == X``.
        # Drift to drop the WHERE would mass-affect every
        # attachment row in the system.
        repo = CustomFieldRepository(session=MagicMock())
        captured: list[Any] = []

        async def _exec(stmt: object) -> Any:
            captured.append(stmt)
            return MagicMock()

        repo.session.execute = AsyncMock(side_effect=_exec)  # type: ignore[method-assign]

        target = uuid4()
        await repo.delete_attachments(target)

        for stmt in captured:
            sql = _compile(stmt).lower()
            assert sql.startswith("delete from")
            assert target.hex in sql.replace("-", "")
