"""Pydantic schemas for work-item attachment endpoints."""

from typing import Annotated

from fastapi import Path
from pydantic import UUID4, Field

from rapidly.core.types import AuditableSchema, IdentifiableSchema, Schema

WorkItemAttachmentID = Annotated[
    UUID4, Path(description="The work-item attachment ID.")
]


class WorkItemAttachment(IdentifiableSchema, AuditableSchema):
    work_item_id: UUID4
    file_id: UUID4
    uploaded_by_id: UUID4 | None


class WorkItemAttachmentCreate(Schema):
    work_item_id: UUID4 = Field(..., description="The work item to attach the file to.")
    file_id: UUID4 = Field(
        ...,
        description=(
            "ID of a file previously uploaded via /files. The file must "
            "belong to the same workspace as the work item's project."
        ),
    )
