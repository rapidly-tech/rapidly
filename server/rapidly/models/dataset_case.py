"""One input/expected-output pair within a Dataset.

The eval runner (M4.8b) loops over a dataset's cases, feeds each
``input_data`` to the workflow under test, captures the
workflow's output, and compares it to ``expected_output`` via a
per-dataset assertion strategy (exact match, JSON-schema
validation, LLM judge — picked when M4.8b lands).

``expected_output`` is nullable: some workflows have no canonical
right answer (e.g., creative-write tasks). For those, the eval
runner records the actual output without scoring — useful for
regression review or for an LLM-judge step that scores on
qualitative criteria.

Ordering:
    ``order_index`` lets the UI render cases in a stable order
    and makes "case 3 failed" a meaningful pointer. Not a unique
    constraint — two cases at the same index are allowed (the
    UI sub-sorts by name); duplicates just mean the operator
    hasn't reordered yet.
"""

from typing import TYPE_CHECKING, Any
from uuid import UUID

from sqlalchemy import ForeignKey, Integer, String, Uuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, declared_attr, mapped_column, relationship

from rapidly.core.db.models.base import BaseEntity

if TYPE_CHECKING:
    from .dataset import Dataset


class DatasetCase(BaseEntity):
    """A single fixture: input_data + optional expected_output."""

    __tablename__ = "agent_dataset_cases"

    dataset_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("agent_datasets.id", ondelete="cascade"),
        nullable=False,
        index=True,
    )

    # Human-facing label for this case ("RFI with concrete spec",
    # "edge case: empty submittal log"). Surfaces in the eval
    # results table so operators can tell which case failed.
    name: Mapped[str] = mapped_column(String(256), nullable=False)

    # The workflow's input. Shape depends on the workflow being
    # tested — JSONB so we can store whatever Pydantic-validated
    # shape the workflow accepts at run-trigger time.
    input_data: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)

    # The expected workflow output. Null when no canonical answer
    # exists; the eval runner records actual_output anyway for
    # qualitative review.
    expected_output: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)

    # Stable display order. Not unique — duplicates allowed
    # during reordering. See module docstring for the rationale.
    order_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    @declared_attr
    def dataset(cls) -> Mapped["Dataset"]:
        return relationship("Dataset", lazy="raise")
