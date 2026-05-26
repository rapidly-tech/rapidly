"""Pydantic schemas for the EvalRun read + trigger API."""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel

from rapidly.models import AssertionStrategy, EvalRunStatus


class EvalRunTrigger(BaseModel):
    """Trigger payload. Workflow version + dataset must be in the
    same workspace as the caller; the action layer enforces both.
    """

    workflow_version_id: UUID
    dataset_id: UUID
    assertion_strategy: AssertionStrategy = AssertionStrategy.exact_match


class EvalRunSchema(BaseModel):
    id: UUID
    workspace_id: UUID
    dataset_id: UUID
    workflow_version_id: UUID
    status: EvalRunStatus
    assertion_strategy: AssertionStrategy
    case_count: int
    pass_count: int
    fail_count: int
    error_count: int
    started_at: datetime | None
    completed_at: datetime | None
    error_message: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class EvalRunCaseSchema(BaseModel):
    id: UUID
    eval_run_id: UUID
    case_id: UUID | None
    run_id: UUID | None
    case_name: str
    case_input_data: dict[str, Any]
    case_expected_output: dict[str, Any] | None
    actual_output: dict[str, Any] | None
    passed: bool | None
    error_message: str | None
    duration_ms: int | None
    created_at: datetime

    model_config = {"from_attributes": True}
