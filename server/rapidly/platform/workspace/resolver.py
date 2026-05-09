"""Workspace resolver: extract org from request payloads or auth context.

Provides ``get_payload_workspace`` which resolves an ``WorkspaceID``
path/query parameter into a loaded ``Workspace`` model instance,
enforcing membership and soft-delete checks.
"""

from typing import Protocol

from pydantic import UUID4
from sqlalchemy import select

from rapidly.errors import RequestValidationError, validation_error
from rapidly.identity.auth.models import AuthPrincipal, is_workspace_principal
from rapidly.models import User, Workspace, WorkspaceMembership
from rapidly.postgres import AsyncSession


class _WorkspaceUUIDModelNone(Protocol):
    workspace_id: UUID4 | None


class _WorkspaceUUIDModel(Protocol):
    workspace_id: UUID4


WorkspaceUUIDModel = _WorkspaceUUIDModelNone | _WorkspaceUUIDModel


async def get_payload_workspace(
    session: AsyncSession,
    auth_subject: AuthPrincipal[User | Workspace],
    model: WorkspaceUUIDModel,
) -> Workspace:
    # Avoids a circular import :(

    if is_workspace_principal(auth_subject):
        if model.workspace_id is not None:
            raise RequestValidationError(
                [
                    {
                        "type": "workspace_token",
                        "msg": (
                            "Setting workspace_id is disallowed "
                            "when using an workspace token."
                        ),
                        "loc": (
                            "body",
                            "workspace_id",
                        ),
                        "input": model.workspace_id,
                    }
                ]
            )
        return auth_subject.subject

    if model.workspace_id is None:
        raise RequestValidationError(
            [
                {
                    "type": "missing",
                    "msg": "workspace_id is required.",
                    "loc": (
                        "body",
                        "workspace_id",
                    ),
                    "input": None,
                }
            ]
        )

    statement = select(Workspace).where(
        Workspace.id == model.workspace_id,
        Workspace.id.in_(
            select(WorkspaceMembership.workspace_id).where(
                WorkspaceMembership.user_id == auth_subject.subject.id,
                WorkspaceMembership.deleted_at.is_(None),
            )
        ),
    )
    result = await session.execute(statement)
    workspace = result.scalar_one_or_none()

    if workspace is None:
        raise RequestValidationError(
            [
                validation_error(
                    "workspace_id", "Workspace not found.", model.workspace_id
                )
            ]
        )

    return workspace
