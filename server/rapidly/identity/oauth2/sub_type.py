"""OAuth2 subject-type discriminator and token sub-type model.

Defines ``SubType`` (user vs workspace) and ``SubTypeValue``, the
polymorphic helper that resolves an access token's ``sub`` claim into
the correct entity.
"""

from enum import StrEnum
from typing import TYPE_CHECKING, Literal, TypeGuard
from uuid import UUID

from sqlalchemy import ForeignKey, String, Uuid
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import Mapped, declared_attr, mapped_column, relationship

if TYPE_CHECKING:
    from rapidly.models import User, Workspace


class SubType(StrEnum):
    user = "user"
    workspace = "workspace"


SubTypeValue = tuple[SubType, "User | Workspace"]


def is_sub_user(v: SubTypeValue) -> TypeGuard[tuple[Literal[SubType.user], "User"]]:
    return v[0] == SubType.user


def is_sub_workspace(
    v: SubTypeValue,
) -> TypeGuard[tuple[Literal[SubType.workspace], "Workspace"]]:
    return v[0] == SubType.workspace


class SubTypeModelMixin:
    sub_type: Mapped[SubType] = mapped_column(String, nullable=False)
    user_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="cascade"), nullable=True
    )
    workspace_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("workspaces.id", ondelete="cascade"), nullable=True
    )

    @declared_attr
    def user(cls) -> Mapped["User | None"]:
        return relationship("User", lazy="joined")

    @declared_attr
    def workspace(cls) -> Mapped["Workspace | None"]:
        return relationship("Workspace", lazy="joined")

    @hybrid_property
    def sub(self) -> "User | Workspace":
        sub: User | Workspace | None = None
        if self.sub_type == SubType.user:
            sub = self.user
        elif self.sub_type == SubType.workspace:
            sub = self.workspace
        else:
            raise NotImplementedError()

        if sub is None:
            raise ValueError("Sub is not found.")

        return sub

    @sub.inplace.setter
    def _sub_setter(self, value: "User | Workspace") -> None:
        if self.sub_type == SubType.user:
            self.user_id = value.id
        elif self.sub_type == SubType.workspace:
            self.workspace_id = value.id
        else:
            raise NotImplementedError()

    def get_sub_type_value(self) -> SubTypeValue:
        return self.sub_type, self.sub
