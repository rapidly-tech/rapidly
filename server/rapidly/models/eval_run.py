"""An evaluation run — drives a workflow against every case in a dataset.

The eval runner actor (M4.8b) creates one EvalRun row per
``trigger_eval`` API call, then walks the dataset's cases:

1. For each case, create a synthetic Run (the existing
   workflow-execution Run, tagged with ``triggered_by_kind="eval"``)
2. Drive the engine via ``walk_run`` inline
3. Compare the workflow's output_data to the case's
   expected_output via the per-EvalRun assertion strategy
4. Write an EvalRunCase row capturing the result
5. Update the EvalRun's summary counters + status

Why one EvalRun owns N Runs instead of standalone case-execution:
    The existing engine already persists per-step NodeRun rows
    + emits LlmUsage attribution under the parent Run. Reusing
    the Run row gets us all of that for free — operators
    debugging a failing eval case can drill into the same
    NodeRun timeline they use for production runs.

Assertion strategies (v1 = exact_match only):
    - ``exact_match`` — Python ``==`` on actual_output vs
      expected_output. Robust for structured workflows
      (extraction, classification); brittle for free-text
      LLM outputs.
    - ``json_schema`` (M4.8c) — validate actual_output against
      expected_output treated as JSON Schema. Looser than
      exact-match; lets the case author target shape, not value.
    - ``llm_judge`` (M4.8d) — pass actual + expected to a
      grader LLM with a per-case rubric. Most flexible; costs
      tokens.

Status state machine (subset of RunStatus, kept here for
clarity — eval runs don't have ``awaiting_human``):
    pending → running → succeeded | failed | cancelled
"""

from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import TIMESTAMP, ForeignKey, Integer, Text, Uuid
from sqlalchemy.orm import Mapped, declared_attr, mapped_column, relationship

from rapidly.core.db.models.base import BaseEntity
from rapidly.core.extensions.sqlalchemy import StringEnum

if TYPE_CHECKING:
    from .dataset import Dataset
    from .workflow_version import WorkflowVersion
    from .workspace import Workspace


class EvalRunStatus(StrEnum):
    pending = "pending"
    running = "running"
    succeeded = "succeeded"
    failed = "failed"
    cancelled = "cancelled"


class AssertionStrategy(StrEnum):
    exact_match = "exact_match"
    # JSON-Schema validation. The case's ``expected_output`` is
    # treated as a JSON Schema (not a concrete value); the case
    # passes when ``actual_output`` validates against it. Useful
    # when the workflow's output shape is stable but specific
    # field values are non-deterministic (LLM extraction
    # producing varying paraphrases of the same field).
    json_schema = "json_schema"
    # llm_judge lands in M4.8d.


TERMINAL_EVAL_RUN_STATUSES: frozenset[EvalRunStatus] = frozenset(
    {EvalRunStatus.succeeded, EvalRunStatus.failed, EvalRunStatus.cancelled}
)


class EvalRun(BaseEntity):
    """A single evaluation pass over a dataset against a workflow version."""

    __tablename__ = "agent_eval_runs"

    workspace_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("workspaces.id", ondelete="cascade"),
        nullable=False,
        index=True,
    )
    dataset_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("agent_datasets.id", ondelete="restrict"),
        nullable=False,
        index=True,
    )
    # Restrict (not cascade) on workflow_version: the eval is a
    # snapshot of what that version produced; deleting the version
    # would invalidate the eval's reference. Operators rotate
    # versions; eval rows survive.
    workflow_version_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("workflow_versions.id", ondelete="restrict"),
        nullable=False,
        index=True,
    )

    status: Mapped[EvalRunStatus] = mapped_column(
        StringEnum(EvalRunStatus, length=16),
        nullable=False,
        default=EvalRunStatus.pending,
    )
    assertion_strategy: Mapped[AssertionStrategy] = mapped_column(
        StringEnum(AssertionStrategy, length=32),
        nullable=False,
        default=AssertionStrategy.exact_match,
    )

    # Per-eval summary counters. Populated incrementally by the
    # actor; final values surface in the API response so
    # dashboards don't have to count rows.
    case_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    pass_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    fail_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    started_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    @declared_attr
    def workspace(cls) -> Mapped["Workspace"]:
        return relationship("Workspace", lazy="raise")

    @declared_attr
    def dataset(cls) -> Mapped["Dataset"]:
        return relationship("Dataset", lazy="raise")

    @declared_attr
    def workflow_version(cls) -> Mapped["WorkflowVersion"]:
        return relationship("WorkflowVersion", lazy="raise")
