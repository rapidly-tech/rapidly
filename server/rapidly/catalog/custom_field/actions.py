"""Custom field CRUD with slug uniqueness enforcement and JSONB cascade updates."""

import uuid
from collections.abc import Sequence
from typing import Any

from sqlalchemy import (
    UnaryExpression,
    asc,
    desc,
)

from rapidly.catalog.custom_field.ordering import CustomFieldSortProperty
from rapidly.core.ordering import Sorting
from rapidly.core.pagination import PaginationParams, paginate
from rapidly.errors import RequestValidationError, validation_error
from rapidly.identity.auth.models import (
    AuthPrincipal,
)
from rapidly.models import CustomField, User, Workspace
from rapidly.models.custom_field import CustomFieldType
from rapidly.platform.workspace.resolver import get_payload_workspace
from rapidly.postgres import AsyncReadSession, AsyncSession

from .queries import CustomFieldRepository
from .types import CustomFieldCreate, CustomFieldUpdate


class CustomFieldService:
    """Manage workspace-scoped custom fields with JSONB propagation on rename."""

    # ── Queries ────────────────────────────────────────────────────────

    async def list_custom_fields(
        self,
        session: AsyncReadSession,
        auth_subject: AuthPrincipal[User | Workspace],
        *,
        workspace_id: Sequence[uuid.UUID] | None = None,
        query: str | None = None,
        type: Sequence[CustomFieldType] | None = None,
        pagination: PaginationParams,
        sorting: Sequence[Sorting[CustomFieldSortProperty]] = (
            (CustomFieldSortProperty.slug, False),
        ),
    ) -> tuple[Sequence[CustomField], int]:
        repo = CustomFieldRepository.from_session(session)
        stmt = repo.get_readable_statement(auth_subject)
        stmt = repo.apply_list_filters(
            stmt, workspace_id=workspace_id, query=query, type=type
        )
        stmt = stmt.order_by(*self._resolve_ordering(sorting))
        return await paginate(session, stmt, pagination=pagination)

    async def get_by_id(
        self,
        session: AsyncReadSession,
        auth_subject: AuthPrincipal[User | Workspace],
        id: uuid.UUID,
    ) -> CustomField | None:
        repo = CustomFieldRepository.from_session(session)
        return await repo.get_readable_by_id(auth_subject, id)

    # ── Mutations ─────────────────────────────────────────────────────

    async def create(
        self,
        session: AsyncSession,
        custom_field_create: CustomFieldCreate,
        auth_subject: AuthPrincipal[User | Workspace],
    ) -> CustomField:
        org = await get_payload_workspace(session, auth_subject, custom_field_create)
        repo = CustomFieldRepository.from_session(session)
        self._assert_slug_unique(
            await repo.get_by_workspace_and_slug(org.id, custom_field_create.slug),
            custom_field_create.slug,
        )

        cf = CustomField(
            **custom_field_create.model_dump(exclude={"workspace_id"}, by_alias=True),
            workspace=org,
        )
        await repo.create(cf)
        return cf

    async def update(
        self,
        session: AsyncSession,
        custom_field: CustomField,
        custom_field_update: CustomFieldUpdate,
    ) -> CustomField:
        self._guard_type_immutable(custom_field, custom_field_update)

        repo = CustomFieldRepository.from_session(session)
        new_slug = custom_field_update.slug
        if new_slug is not None and custom_field.slug != new_slug:
            existing = await repo.get_by_workspace_and_slug(
                custom_field.workspace_id, new_slug
            )
            if existing is not None and existing.id != custom_field.id:
                self._assert_slug_unique(existing, new_slug)

        old_slug = custom_field.slug
        for attr, value in custom_field_update.model_dump(
            exclude_unset=True, by_alias=True
        ).items():
            setattr(custom_field, attr, value)

        if old_slug != custom_field.slug:
            await repo.cascade_slug_rename(custom_field, old_slug)

        await repo.update(custom_field)
        return custom_field

    async def delete(
        self, session: AsyncSession, custom_field: CustomField
    ) -> CustomField:
        custom_field.set_deleted_at()

        repo = CustomFieldRepository.from_session(session)
        await repo.update(custom_field)
        await repo.delete_attachments(custom_field.id)
        return custom_field

    async def get_by_workspace_and_id(
        self, session: AsyncSession, id: uuid.UUID, workspace_id: uuid.UUID
    ) -> CustomField | None:
        repo = CustomFieldRepository.from_session(session)
        return await repo.get_by_workspace_and_id(id, workspace_id)

    # ── Private helpers ───────────────────────────────────────────────

    @staticmethod
    def _assert_slug_unique(existing: CustomField | None, slug: str) -> None:
        if existing is not None:
            raise RequestValidationError(
                [
                    validation_error(
                        "slug", "Custom field with this slug already exists.", slug
                    )
                ]
            )

    @staticmethod
    def _guard_type_immutable(field: CustomField, patch: CustomFieldUpdate) -> None:
        if field.type != patch.type:
            raise RequestValidationError(
                [
                    validation_error(
                        "type",
                        "The type of a custom field cannot be changed.",
                        patch.type,
                    )
                ]
            )

    @staticmethod
    def _resolve_ordering(
        sorting: Sequence[Sorting[CustomFieldSortProperty]],
    ) -> list[UnaryExpression[Any]]:
        clauses: list[UnaryExpression[Any]] = []
        for criterion, is_desc in sorting:
            fn = desc if is_desc else asc
            clauses.append(fn(criterion))
        return clauses


custom_field = CustomFieldService()
