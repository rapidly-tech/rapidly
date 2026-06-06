"""Pydantic schemas for the federated-model API surface."""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel

from rapidly.models.federated_model import ModelStatus


class FederatedModelCreate(BaseModel):
    """Request payload for creating a federated model record.

    The actual IFC bytes upload via the existing ``catalog/file``
    presigned-PUT flow; this call wires that uploaded file_id into a
    new FederatedModel row in ``status='uploaded'`` so the parser
    worker (M3.1b) can pick it up.
    """

    project_id: UUID
    name: str
    source_file_id: UUID


class FederatedModelSchema(BaseModel):
    id: UUID
    project_id: UUID
    name: str
    source_file_id: UUID
    xkt_file_id: UUID | None
    status: ModelStatus
    units: str | None
    element_count: int | None
    bbox: dict[str, Any] | None
    error_message: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ModelDisciplineSchema(BaseModel):
    id: UUID
    model_id: UUID
    name: str
    element_count: int

    model_config = {"from_attributes": True}
