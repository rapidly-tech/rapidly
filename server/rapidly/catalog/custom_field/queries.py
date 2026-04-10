"""Custom field persistence layer.

``CustomFieldRepository`` handles workspace-scoped lookups,
slug-uniqueness checks, attachment cascade deletes, and
JSONB key-rename propagation on slug changes.
"""

import uuid
from collections.abc import Sequence

from sqlalchemy import Select, delete, func, or_, select, update
from sqlalchemy.orm import contains_eager

from rapidly.core.queries import Repository, SoftDeleteMixin
from rapidly.core.queries.utils import escape_like
from rapidly.identity.auth.models import (
    AuthPrincipal,
    User,
    Workspace,
    is_user_principal,
    is_workspace_principal,
)
from rapidly.models import CustomField, WorkspaceMembership
from rapidly.models.custom_field import CustomFieldType

from .attachment import attached_custom_fields_models
from .data import custom_field_data_models


class CustomFieldRepository(
    SoftDeleteMixin[CustomField],
    Repository[CustomField],
):
    """Custom field queries with workspace scoping and JSONB propagation."""

    model = CustomField

    # ── Reads ──

    def get_readable_statement(
        self, auth_subject: AuthPrincipal[User | Workspace]
    ) -> Select[tuple[CustomField]]:
        stmt = (
            select(CustomField)
            .where(CustomField.deleted_at.is_(None))
            .join(Workspace, Workspace.id == CustomField.workspace_id)
            .options(contains_eager(CustomField.workspace))
        )

        if is_user_principal(auth_subject):
            stmt = stmt.where(
                CustomField.workspace_id.in_(
                    select(WorkspaceMembership.workspace_id).where(
                        WorkspaceMembership.user_id == auth_subject.subject.id,
                        WorkspaceMembership.deleted_at.is_(None),
                    )
                )
            )
        elif is_workspace_principal(auth_subject):
            stmt = stmt.where(
                CustomField.workspace_id == auth_subject.subject.id,
            )

        return stmt

    def apply_list_filters(
        self,
        stmt: Select[tuple[CustomField]],
        *,
        workspace_id: Sequence[uuid.UUID] | None = None,
        query: str | None = None,
        type: Sequence[CustomFieldType] | None = None,
    ) -> Select[tuple[CustomField]]:
        if workspace_id is not None:
            stmt = stmt.where(CustomField.workspace_id.in_(workspace_id))
        if query is not None:
            escaped = escape_like(query)
            stmt = stmt.where(
                or_(
                    CustomField.name.ilike(f"%{escaped}%"),
                    CustomField.slug.ilike(f"%{escaped}%"),
                )
            )
        if type is not None:
            stmt = stmt.where(CustomField.type.in_(type))
        return stmt

    async def get_readable_by_id(
        self,
        auth_subject: AuthPrincipal[User | Workspace],
        id: uuid.UUID,
    ) -> CustomField | None:
        stmt = self.get_readable_statement(auth_subject).where(CustomField.id == id)
        return await self.get_one_or_none(stmt)

    async def get_by_workspace_and_id(
        self, id: uuid.UUID, workspace_id: uuid.UUID
    ) -> CustomField | None:
        stmt = select(CustomField).where(
            CustomField.deleted_at.is_(None),
            CustomField.workspace_id == workspace_id,
            CustomField.id == id,
        )
        return await self.get_one_or_none(stmt)

    async def get_by_workspace_and_slug(
        self, workspace_id: uuid.UUID, slug: str
    ) -> CustomField | None:
        stmt = select(CustomField).where(
            CustomField.workspace_id == workspace_id,
            CustomField.slug == slug,
        )
        return await self.get_one_or_none(stmt)

    # ── Writes ──

    async def delete_attachments(self, custom_field_id: uuid.UUID) -> None:
        """Remove all attachment rows pointing at the given custom field."""
        for model in attached_custom_fields_models:
            await self.session.execute(
                delete(model).where(model.custom_field_id == custom_field_id)
            )

    async def cascade_slug_rename(self, cf: CustomField, old_slug: str) -> None:
        """Rename the key in every JSONB ``custom_field_data`` column."""
        for model in custom_field_data_models:
            stmt = (
                update(model)
                .where(
                    model.workspace == cf.workspace,
                    model.custom_field_data.has_key(old_slug),
                )
                .values(
                    custom_field_data=(model.custom_field_data.op("-")(old_slug)).op(
                        "||"
                    )(
                        func.jsonb_build_object(
                            cf.slug,
                            model.custom_field_data[old_slug],
                        )
                    )
                )
            )
            await self.session.execute(stmt)
