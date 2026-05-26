"""Pydantic schemas for the dataset + case API surface."""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class DatasetCreate(BaseModel):
    workspace_id: UUID
    name: str = Field(min_length=1, max_length=256)
    description: str | None = Field(default=None, max_length=4096)


class DatasetUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=256)
    description: str | None = Field(default=None, max_length=4096)


class DatasetSchema(BaseModel):
    id: UUID
    workspace_id: UUID
    name: str
    description: str | None
    created_at: datetime
    modified_at: datetime | None

    model_config = {"from_attributes": True}


class DatasetCaseCreate(BaseModel):
    """Create payload. ``dataset_id`` comes from the URL path, not
    the body — keeps the API surface uniform with the other
    nested-resource endpoints in the agents chamber.
    """

    name: str = Field(min_length=1, max_length=256)
    input_data: dict[str, Any] = Field(
        description="The workflow input fixture. Shape matches the target workflow."
    )
    expected_output: dict[str, Any] | None = Field(
        default=None,
        description=(
            "Optional canonical workflow output. Null for cases "
            "without a right answer (creative tasks, qualitative review)."
        ),
    )
    order_index: int = Field(default=0, ge=0)


class DatasetCaseUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=256)
    input_data: dict[str, Any] | None = None
    expected_output: dict[str, Any] | None = None
    order_index: int | None = Field(default=None, ge=0)


class DatasetCaseSchema(BaseModel):
    id: UUID
    dataset_id: UUID
    name: str
    input_data: dict[str, Any]
    expected_output: dict[str, Any] | None
    order_index: int
    created_at: datetime
    modified_at: datetime | None

    model_config = {"from_attributes": True}
