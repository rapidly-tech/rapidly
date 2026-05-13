"""Pydantic schemas for user favorite endpoints."""

from typing import Annotated

from fastapi import Path
from pydantic import UUID4

from rapidly.core.types import AuditableSchema, IdentifiableSchema, Schema
from rapidly.models import UserFavoriteEntityType

UserFavoriteID = Annotated[UUID4, Path(description="The user favorite ID.")]


class UserFavorite(IdentifiableSchema, AuditableSchema):
    user_id: UUID4
    entity_type: UserFavoriteEntityType
    entity_id: UUID4


class UserFavoriteCreate(Schema):
    entity_type: UserFavoriteEntityType
    entity_id: UUID4
