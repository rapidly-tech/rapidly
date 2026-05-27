"""Unit tests for the ``llm_judge`` assertion strategy (M4.8d).

We don't make real LLM calls — the test provider in pydantic-ai
returns a deterministic stub. The point of these tests is that
the dispatch wiring is correct: the judge sees the EXPECTED +
ACTUAL JSON in its prompt and the comparator reads ``passed``
from the structured output back.
"""

from __future__ import annotations

from typing import Any

import pytest
from pytest_mock import MockerFixture

from rapidly.agents.eval_run import workers as eval_workers
from rapidly.agents.eval_run.workers import _compare, _safe_dump
from rapidly.models import AssertionStrategy, EvalRun


def _make_eval_run(
    *,
    judge_model_id: str | None = "test:stub",
) -> EvalRun:
    return EvalRun(
        assertion_strategy=AssertionStrategy.llm_judge,
        judge_model_id=judge_model_id,
    )


@pytest.mark.asyncio
class TestLlmJudgeStrategy:
    async def test_routes_through_structured_output_handler(
        self,
        mocker: MockerFixture,
    ) -> None:
        # Patch the structured_output_handler to capture what the
        # judge dispatch builds — pin the prompt + schema shape
        # without needing a real LLM round-trip.
        captured: dict[str, Any] = {}

        async def _stub(
            ctx: dict[str, Any],
            cfg: dict[str, Any],
            inp: dict[str, Any],
        ) -> dict[str, Any]:
            captured["ctx"] = ctx
            captured["cfg"] = cfg
            captured["inp"] = inp
            return {
                "data": {"passed": True, "reason": "looks good"},
                "usage": {"input_tokens": 0, "output_tokens": 0},
            }

        mocker.patch.object(eval_workers, "structured_output_handler", _stub)

        eval_run = _make_eval_run(judge_model_id="openai:gpt-4o-mini")
        passed = await _compare(
            session=object(),  # ctx pass-through, judge stub ignores it
            eval_run=eval_run,
            actual={"summary": "Concrete spec attached"},
            expected={"criteria": "ACTUAL describes a concrete specification."},
        )
        assert passed is True

        # Provider + model split out correctly.
        assert captured["cfg"]["provider"] == "openai"
        assert captured["cfg"]["model"] == "gpt-4o-mini"
        # Output schema pins ``passed`` + (optional) ``reason``.
        schema = captured["cfg"]["schema_json"]
        assert schema["required"] == ["passed"]
        assert schema["properties"]["passed"]["type"] == "boolean"
        # The judge sees both EXPECTED + ACTUAL serialised into
        # the prompt input.
        assert "ACTUAL describes" in captured["inp"]["expected"]
        assert "Concrete spec" in captured["inp"]["actual"]

    async def test_returns_false_when_judge_says_so(
        self,
        mocker: MockerFixture,
    ) -> None:
        async def _stub(
            ctx: dict[str, Any],
            cfg: dict[str, Any],
            inp: dict[str, Any],
        ) -> dict[str, Any]:
            return {
                "data": {"passed": False, "reason": "missed the criterion"},
                "usage": {"input_tokens": 0, "output_tokens": 0},
            }

        mocker.patch.object(eval_workers, "structured_output_handler", _stub)

        passed = await _compare(
            session=object(),
            eval_run=_make_eval_run(),
            actual={"x": 1},
            expected={"criteria": "anything"},
        )
        assert passed is False

    async def test_missing_judge_model_raises(self) -> None:
        # The trigger endpoint guards against creating an
        # llm_judge eval without a judge_model_id, but the
        # comparator double-checks at run time too — if some
        # internal path bypassed the trigger guard (eval_run
        # row hand-inserted, future API for cloning evals), we
        # don't want a quiet pass.
        eval_run = _make_eval_run(judge_model_id=None)
        with pytest.raises(ValueError, match="judge_model_id"):
            await _compare(
                session=object(),
                eval_run=eval_run,
                actual={"x": 1},
                expected={"y": 1},
            )

    async def test_rejects_judge_model_without_colon(self) -> None:
        # Same provider:model contract the LLM + embedder
        # dispatch enforces — a free-form name without a
        # provider prefix is a config error.
        eval_run = _make_eval_run(judge_model_id="just-a-model-name")
        with pytest.raises(ValueError, match="provider:model"):
            await _compare(
                session=object(),
                eval_run=eval_run,
                actual={"x": 1},
                expected={"y": 1},
            )

    async def test_passed_defaults_to_false_when_missing_from_judge(
        self,
        mocker: MockerFixture,
    ) -> None:
        # Defensive: if the judge somehow returns malformed
        # output (missing ``passed`` field — should be
        # impossible given the schema, but a model with sloppy
        # function-call adherence could do it), default to
        # False rather than treating a missing key as a pass.
        async def _stub(
            ctx: dict[str, Any],
            cfg: dict[str, Any],
            inp: dict[str, Any],
        ) -> dict[str, Any]:
            return {
                "data": {"reason": "forgot to set passed"},
                "usage": {"input_tokens": 0, "output_tokens": 0},
            }

        mocker.patch.object(eval_workers, "structured_output_handler", _stub)

        passed = await _compare(
            session=object(),
            eval_run=_make_eval_run(),
            actual={"x": 1},
            expected={"y": 1},
        )
        assert passed is False


class TestSafeDump:
    def test_serialises_json_compatible_dict(self) -> None:
        out = _safe_dump({"a": 1, "b": "two", "c": [3, 4]})
        # sort_keys=True for deterministic prompts across
        # iterations (judge sees the same prompt order regardless
        # of how the workflow author wrote the case).
        assert out == '{"a": 1, "b": "two", "c": [3, 4]}'

    def test_falls_back_to_repr_on_non_serialisable(self) -> None:
        # Pretend a workflow emits a non-JSON object (e.g., a
        # datetime). The judge still gets a stringified view
        # instead of the comparator erroring out.
        class _Thing:
            def __repr__(self) -> str:
                return "<Thing>"

        out = _safe_dump({"x": _Thing()})
        assert "<Thing>" in out
