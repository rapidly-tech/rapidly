"""Unit tests for the ``json_schema`` assertion strategy (M4.8c).

End-to-end runner coverage stays in ``test_workers.py``; this
file pins the comparator's behaviour against representative
schemas without the engine overhead.
"""

from __future__ import annotations

from typing import Any

import pytest

from rapidly.agents.eval_run.workers import _compare
from rapidly.models import AssertionStrategy, EvalRun


def _make_eval_run(strategy: AssertionStrategy) -> EvalRun:
    """Build a bare EvalRun for the comparator. The comparator
    only reads ``assertion_strategy`` + (for llm_judge) the
    workspace_id/judge_model_id — everything else can stay
    unset for these unit tests.
    """
    return EvalRun(assertion_strategy=strategy)


async def _compare_sync(
    *,
    strategy: AssertionStrategy,
    actual: dict[str, Any],
    expected: dict[str, Any],
) -> bool:
    """Sync-style wrapper around the async comparator for tests
    that don't need to drive the LLM path. session is unused for
    exact_match + json_schema.
    """
    passed, _reason = await _compare(
        session=None,
        eval_run=_make_eval_run(strategy),
        actual=actual,
        expected=expected,
    )
    return passed


@pytest.mark.asyncio
class TestJsonSchemaStrategy:
    async def test_passes_when_actual_matches_required_keys_and_types(
        self,
    ) -> None:
        passed = await _compare_sync(
            strategy=AssertionStrategy.json_schema,
            actual={"status": "open", "count": 3, "note": "extra field is OK"},
            expected={
                "type": "object",
                "required": ["status", "count"],
                "properties": {
                    "status": {"type": "string"},
                    "count": {"type": "integer"},
                },
            },
        )
        assert passed is True

    async def test_fails_on_missing_required_key(self) -> None:
        passed = await _compare_sync(
            strategy=AssertionStrategy.json_schema,
            actual={"count": 3},
            expected={
                "type": "object",
                "required": ["status", "count"],
                "properties": {
                    "status": {"type": "string"},
                    "count": {"type": "integer"},
                },
            },
        )
        assert passed is False

    async def test_fails_on_wrong_type(self) -> None:
        passed = await _compare_sync(
            strategy=AssertionStrategy.json_schema,
            actual={"status": "open", "count": "three"},
            expected={
                "type": "object",
                "required": ["count"],
                "properties": {
                    "count": {"type": "integer"},
                },
            },
        )
        assert passed is False

    async def test_passes_when_required_array_has_correct_item_type(
        self,
    ) -> None:
        passed = await _compare_sync(
            strategy=AssertionStrategy.json_schema,
            actual={"tags": ["concrete", "spec"]},
            expected={
                "type": "object",
                "required": ["tags"],
                "properties": {
                    "tags": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                },
            },
        )
        assert passed is True

    async def test_fails_on_array_with_wrong_item_type(self) -> None:
        passed = await _compare_sync(
            strategy=AssertionStrategy.json_schema,
            actual={"tags": [1, 2, 3]},
            expected={
                "type": "object",
                "required": ["tags"],
                "properties": {
                    "tags": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                },
            },
        )
        assert passed is False

    async def test_passes_with_enum_constraint(self) -> None:
        passed = await _compare_sync(
            strategy=AssertionStrategy.json_schema,
            actual={"label": "urgent"},
            expected={
                "type": "object",
                "required": ["label"],
                "properties": {
                    "label": {
                        "type": "string",
                        "enum": ["low", "high", "urgent"],
                    },
                },
            },
        )
        assert passed is True

    async def test_fails_on_enum_violation(self) -> None:
        passed = await _compare_sync(
            strategy=AssertionStrategy.json_schema,
            actual={"label": "unknown-label"},
            expected={
                "type": "object",
                "required": ["label"],
                "properties": {
                    "label": {
                        "type": "string",
                        "enum": ["low", "high", "urgent"],
                    },
                },
            },
        )
        assert passed is False

    async def test_passes_on_nested_object(self) -> None:
        passed = await _compare_sync(
            strategy=AssertionStrategy.json_schema,
            actual={"file": {"name": "drawing.pdf", "size": 1024}},
            expected={
                "type": "object",
                "required": ["file"],
                "properties": {
                    "file": {
                        "type": "object",
                        "required": ["name"],
                        "properties": {
                            "name": {"type": "string"},
                            "size": {"type": "integer"},
                        },
                    },
                },
            },
        )
        assert passed is True


@pytest.mark.asyncio
class TestExactMatchUnchanged:
    """Regression: M4.8b's exact_match strategy keeps its
    semantics after M4.8c/d add new dispatch cases.
    """

    async def test_passes_on_equal_dicts(self) -> None:
        passed = await _compare_sync(
            strategy=AssertionStrategy.exact_match,
            actual={"x": 1, "y": 2},
            expected={"x": 1, "y": 2},
        )
        assert passed is True

    async def test_fails_on_extra_field(self) -> None:
        passed = await _compare_sync(
            strategy=AssertionStrategy.exact_match,
            actual={"x": 1, "y": 2, "z": 3},
            expected={"x": 1, "y": 2},
        )
        assert passed is False
