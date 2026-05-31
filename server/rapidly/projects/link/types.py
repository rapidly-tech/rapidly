"""Pydantic schemas for work-item relation endpoints."""

from typing import Annotated

from fastapi import Path
from pydantic import UUID4, Field

from rapidly.core.types import AuditableSchema, IdentifiableSchema, Schema
from rapidly.models.work_item_relation import WorkItemRelationType

WorkItemRelationID = Annotated[UUID4, Path(description="The work-item relation ID.")]


class WorkItemRelation(IdentifiableSchema, AuditableSchema):
    work_item_id: UUID4
    related_id: UUID4
    relation_type: WorkItemRelationType


class WorkItemRelationCreate(Schema):
    work_item_id: UUID4 = Field(..., description="The originating work item.")
    related_id: UUID4 = Field(..., description="The target work item.")
    relation_type: WorkItemRelationType
