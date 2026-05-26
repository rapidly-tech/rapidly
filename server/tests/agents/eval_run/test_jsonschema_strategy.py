"""Unit tests for the ``json_schema`` assertion strategy (M4.8c).

End-to-end runner coverage stays in ``test_workers.py``; this
file pins the comparator's behaviour against representative
schemas without the engine overhead.
"""

from __future__ import annotations

from rapidly.agents.eval_run.workers import _compare
from rapidly.models import AssertionStrategy


class TestJsonSchemaStrategy:
    def test_passes_when_actual_matches_required_keys_and_types(self) -> None:
        # Expected is a schema: actual must be an object with
        # a string ``status`` and integer ``count``.
        passed = _compare(
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

    def test_fails_on_missing_required_key(self) -> None:
        passed = _compare(
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

    def test_fails_on_wrong_type(self) -> None:
        # ``count`` is required to be integer; got string.
        passed = _compare(
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

    def test_passes_when_required_array_has_correct_item_type(self) -> None:
        passed = _compare(
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

    def test_fails_on_array_with_wrong_item_type(self) -> None:
        passed = _compare(
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

    def test_passes_with_enum_constraint(self) -> None:
        # Enum-style allowed values — useful for classification
        # workflows where actual is one of N labels.
        passed = _compare(
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

    def test_fails_on_enum_violation(self) -> None:
        passed = _compare(
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

    def test_passes_on_nested_object(self) -> None:
        passed = _compare(
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


class TestExactMatchUnchanged:
    """Regression: M4.8b's exact_match strategy keeps its
    semantics after the new dispatch case is added.
    """

    def test_passes_on_equal_dicts(self) -> None:
        passed = _compare(
            strategy=AssertionStrategy.exact_match,
            actual={"x": 1, "y": 2},
            expected={"x": 1, "y": 2},
        )
        assert passed is True

    def test_fails_on_extra_field(self) -> None:
        # Distinction from json_schema: exact_match rejects
        # extra fields. Same actual would pass under
        # json_schema if the schema didn't forbid additional
        # properties.
        passed = _compare(
            strategy=AssertionStrategy.exact_match,
            actual={"x": 1, "y": 2, "z": 3},
            expected={"x": 1, "y": 2},
        )
        assert passed is False
