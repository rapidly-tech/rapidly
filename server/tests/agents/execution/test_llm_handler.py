"""Tests for the LLM + structured-output node handlers.

Uses pydantic-ai's ``TestModel`` so the tests run without network
or credentials. The provider dispatch + prompt rendering + schema
projection are the unit-level concerns; integration with real
providers is exercised in M4.4-followup integration tests.
"""

from __future__ import annotations

import pytest

from rapidly.agents.execution.handlers.llm import (
    LlmNodeError,
    _json_schema_to_pydantic_model,
    _render_prompt,
    llm_handler,
    structured_output_handler,
)


class TestPromptRender:
    def test_substitutes_keys(self) -> None:
        out = _render_prompt(
            "Hello {name}, your score is {score}", {"name": "Ada", "score": 99}
        )
        assert out == "Hello Ada, your score is 99"

    def test_missing_key_leaves_token(self) -> None:
        # Missing key is intentionally permissive — the operator
        # can see the literal in the LLM output and fix the wiring.
        out = _render_prompt("Hi {missing}", {})
        assert out == "Hi {missing}"


class TestJsonSchemaToPydantic:
    def test_required_and_optional_fields(self) -> None:
        schema = {
            "type": "object",
            "required": ["name"],
            "properties": {
                "name": {"type": "string"},
                "age": {"type": "integer"},
            },
        }
        from pydantic import ValidationError

        Model = _json_schema_to_pydantic_model(schema)
        # Required field must be present.
        with pytest.raises(ValidationError):
            Model()
        ok = Model(name="Ada")
        assert ok.name == "Ada"
        assert ok.age is None

    def test_array_items_typed(self) -> None:
        schema = {
            "type": "object",
            "required": ["tags"],
            "properties": {
                "tags": {"type": "array", "items": {"type": "string"}},
            },
        }
        Model = _json_schema_to_pydantic_model(schema)
        ok = Model(tags=["a", "b"])
        assert ok.tags == ["a", "b"]

    def test_rejects_non_object_root(self) -> None:
        with pytest.raises(LlmNodeError, match="must be a JSON Schema"):
            _json_schema_to_pydantic_model({"type": "string"})


@pytest.mark.asyncio
class TestLlmHandlerValidation:
    async def test_requires_provider_and_model(self) -> None:
        with pytest.raises(LlmNodeError, match="provider and model are required"):
            await llm_handler({}, {"prompt_template": "hi"}, {})

    async def test_requires_prompt_template(self) -> None:
        with pytest.raises(LlmNodeError, match="prompt_template is required"):
            await llm_handler({}, {"provider": "test", "model": "test"}, {})

    async def test_unknown_provider_raises(self) -> None:
        with pytest.raises(LlmNodeError, match="unknown provider"):
            await llm_handler(
                {},
                {
                    "provider": "nonexistent",
                    "model": "x",
                    "prompt_template": "hi",
                },
                {},
            )


@pytest.mark.asyncio
class TestLlmHandlerTestProvider:
    async def test_test_provider_returns_text(self) -> None:
        # pydantic-ai's TestModel echoes a canned response so we
        # can exercise the handler without an LLM.
        result = await llm_handler(
            {},
            {
                "provider": "test",
                "model": "test",
                "prompt_template": "say hi to {name}",
            },
            {"name": "Ada"},
        )
        assert isinstance(result["text"], str)
        assert "usage" in result
        assert result["usage"]["input_tokens"] >= 0


@pytest.mark.asyncio
class TestStructuredOutputValidation:
    async def test_requires_schema_json(self) -> None:
        with pytest.raises(LlmNodeError, match="schema_json is required"):
            await structured_output_handler(
                {},
                {
                    "provider": "test",
                    "model": "test",
                    "prompt_template": "extract from {input}",
                },
                {},
            )
