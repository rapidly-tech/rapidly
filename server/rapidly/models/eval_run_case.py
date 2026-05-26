"""One case's result within an EvalRun.

Snapshots the case's input + expected_output at run time so
deleting the source DatasetCase doesn't orphan the eval result —
operators can still review historical evals even after
re-shaping a dataset.

Linked to a real ``Run`` row via ``run_id``: each case execution
creates a synthetic Run that drives the engine, and the eval
case captures the Run's id so operators can drill from
"case 7 failed" → the full per-step NodeRun timeline.
"""

from typing import TYPE_CHECKING, Any
from uuid import UUID

from sqlalchemy import Boolean, ForeignKey, Integer, Text, Uuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, declared_attr, mapped_column, relationship

from rapidly.core.db.models.base import BaseEntity

if TYPE_CHECKING:
    from .agent_run import Run
    from .dataset_case import DatasetCase
    from .eval_run import EvalRun


class EvalRunCase(BaseEntity):
    """One case's pass/fail result within an EvalRun."""

    __tablename__ = "agent_eval_run_cases"

    eval_run_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("agent_eval_runs.id", ondelete="cascade"),
        nullable=False,
        index=True,
    )
    # Set-null on case delete so historical evals survive a
    # dataset's case rotation. We have the case's input
    # snapshot below — the FK link is for navigation, not
    # data integrity.
    case_id: Mapped[UUID | None] = mapped_column(
        Uuid,
        ForeignKey("agent_dataset_cases.id", ondelete="set null"),
        nullable=True,
        index=True,
    )
    # Pointer to the synthetic Run that executed this case.
    # Set-null on Run delete (rare; mostly for the case where
    # operators clean up old Run history while keeping eval
    # results).
    run_id: Mapped[UUID | None] = mapped_column(
        Uuid,
        ForeignKey("agent_runs.id", ondelete="set null"),
        nullable=True,
    )

    # Snapshots of what the case looked like at run time.
    # Captured from the DatasetCase row at dispatch — survive
    # case deletes + edits, so an eval is a point-in-time record.
    case_name: Mapped[str] = mapped_column(Text, nullable=False)
    case_input_data: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    case_expected_output: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB, nullable=True
    )

    # The workflow's actual output for this case. Null when the
    # case errored out before completing (error_message is set).
    actual_output: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)

    # Whether the assertion strategy reported a pass. Null when
    # the case errored (couldn't be evaluated) OR when the
    # case has no expected_output (qualitative review).
    passed: Mapped[bool | None] = mapped_column(Boolean, nullable=True)

    # Set when the engine failed the synthetic Run or the
    # comparator raised. Distinct from "passed=False" — an
    # error means we couldn't evaluate, not "the workflow
    # produced the wrong answer".
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)

    @declared_attr
    def eval_run(cls) -> Mapped["EvalRun"]:
        return relationship("EvalRun", lazy="raise")

    @declared_attr
    def case(cls) -> Mapped["DatasetCase | None"]:
        return relationship("DatasetCase", lazy="raise")

    @declared_attr
    def run(cls) -> Mapped["Run | None"]:
        return relationship("Run", lazy="raise")
