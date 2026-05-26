"""LLM + structured-output node handlers.

Both handlers route through pydantic-ai for provider abstraction
+ structured-output via target-pydantic-model. The provider/model
combination is picked at runtime from the node config so a single
workflow can mix providers across nodes.

Credentials path: v1 reads the API key from the node config (the
editor surfaces a workspace-settings dropdown that injects it).
The proper ``IntegrationCredential`` store lands in M4.7; this
handler reads ``api_key`` straight from ``node_config`` for now
and falls back to the corresponding ``OPENAI_API_KEY`` /
``ANTHROPIC_API_KEY`` / ``GOOGLE_API_KEY`` env var if absent.

Why a single dispatch helper for both handlers: building the
pydantic-ai Agent + Model + Provider is the same dance whether
the caller wants text out or a typed object. The handlers
differentiate by passing ``output_type`` (or not) to the Agent.

Test-only path: when ``provider == "test"`` the handler builds a
``pydantic_ai.models.test.TestModel`` so unit tests don't need
network or credentials.
"""

from __future__ import annotations

import os
from typing import Any, cast

from pydantic_ai import Agent

# Lazy provider imports happen inside ``_build_model``. Keeping
# them out of module scope means the test path doesn't pay the
# anthropic/google imports.


class LlmNodeError(RuntimeError):
    """Surfaces to the engine's per-node failure path."""


def _resolve_api_key(provider: str, node_config: dict[str, Any]) -> str | None:
    raw = node_config.get("api_key")
    if isinstance(raw, str) and raw:
        return raw
    env_var = {
        "openai": "OPENAI_API_KEY",
        "anthropic": "ANTHROPIC_API_KEY",
        "google": "GOOGLE_API_KEY",
        "ollama": "OPENAI_API_KEY",  # ollama uses OpenAI-compatible client
    }.get(provider)
    if env_var is None:
        return None
    return os.environ.get(env_var)


def _build_model(provider: str, model: str, node_config: dict[str, Any]) -> Any:
    """Construct the pydantic-ai Model for the given provider + name.

    Imports the provider's module lazily so a workflow that only
    uses, say, the test model doesn't need the anthropic / google
    extras installed.
    """
    if provider == "test":
        from pydantic_ai.models.test import TestModel

        return TestModel()
    if provider in ("openai", "ollama"):
        from pydantic_ai.models.openai import OpenAIChatModel
        from pydantic_ai.providers.openai import OpenAIProvider

        api_key = _resolve_api_key(provider, node_config)
        base_url = node_config.get("base_url")
        kwargs: dict[str, Any] = {}
        if api_key is not None:
            kwargs["api_key"] = api_key
        if isinstance(base_url, str) and base_url:
            kwargs["base_url"] = base_url
        return OpenAIChatModel(model, provider=OpenAIProvider(**kwargs))
    if provider == "anthropic":
        try:
            from pydantic_ai.models.anthropic import AnthropicModel
            from pydantic_ai.providers.anthropic import AnthropicProvider
        except ImportError as exc:
            raise LlmNodeError(
                "anthropic provider not installed — add the [anthropic] extra"
            ) from exc
        api_key = _resolve_api_key(provider, node_config)
        kwargs = {}
        if api_key is not None:
            kwargs["api_key"] = api_key
        return AnthropicModel(model, provider=AnthropicProvider(**kwargs))
    if provider == "google":
        try:
            from pydantic_ai.models.google import GoogleModel
            from pydantic_ai.providers.google import GoogleProvider
        except ImportError as exc:
            raise LlmNodeError(
                "google provider not installed — add the [google] extra"
            ) from exc
        api_key = _resolve_api_key(provider, node_config)
        kwargs = {}
        if api_key is not None:
            kwargs["api_key"] = api_key
        return GoogleModel(model, provider=GoogleProvider(**kwargs))
    raise LlmNodeError(f"unknown provider {provider!r}")


def _render_prompt(template: str, input_data: dict[str, Any]) -> str:
    """Render a prompt template against input_data.

    For v1 we use Python's str.format-mini-language: ``{key}`` in
    the template gets replaced with str(input_data[key]). Missing
    keys are left as-is (no KeyError) so a partial config doesn't
    crash the run; the LLM sees the literal ``{missing}`` token in
    the prompt and the operator can fix the wiring.
    """

    class _SafeDict(dict):  # type: ignore[type-arg]
        def __missing__(self, key: str) -> str:
            return "{" + key + "}"

    return template.format_map(_SafeDict(input_data))


async def llm_handler(
    ctx: dict[str, Any],
    node_config: dict[str, Any],
    input_data: dict[str, Any],
) -> dict[str, Any]:
    """Call an LLM and return the generated text.

    ``node_config`` fields:
        provider: str             "openai" | "anthropic" | "google" | "ollama" | "test"
        model: str                provider-specific name
        prompt_template: str      str.format-style template against input_data
        system_prompt: str        optional
        temperature: float        optional, default 0.7
        api_key: str              optional, overrides env-var fallback
        base_url: str             optional, for OpenAI-compat endpoints
    """
    provider = str(node_config.get("provider", ""))
    model_name = str(node_config.get("model", ""))
    template = node_config.get("prompt_template")
    if not provider or not model_name:
        raise LlmNodeError("provider and model are required")
    if not isinstance(template, str):
        raise LlmNodeError("prompt_template is required")

    prompt = _render_prompt(template, input_data)
    system_prompt = node_config.get("system_prompt", "")

    model = _build_model(provider, model_name, node_config)
    agent: Agent[None, str] = Agent(model, system_prompt=system_prompt)
    try:
        result = await agent.run(prompt)
    except Exception as exc:
        raise LlmNodeError(f"llm call failed: {exc}") from exc

    output = result.output
    return {
        "text": output if isinstance(output, str) else str(output),
        "usage": _extract_usage(result),
    }


async def structured_output_handler(
    ctx: dict[str, Any],
    node_config: dict[str, Any],
    input_data: dict[str, Any],
) -> dict[str, Any]:
    """Call an LLM with a target JSON schema and return structured data.

    ``node_config`` fields are the same as ``llm_handler`` plus:
        schema_json: dict         JSON Schema for the target shape
                                  (object with primitives + arrays;
                                  $ref / oneOf deferred to v2)
    """
    schema = node_config.get("schema_json")
    if not isinstance(schema, dict):
        raise LlmNodeError("schema_json is required and must be a dict")

    provider = str(node_config.get("provider", ""))
    model_name = str(node_config.get("model", ""))
    template = node_config.get("prompt_template")
    if not provider or not model_name:
        raise LlmNodeError("provider and model are required")
    if not isinstance(template, str):
        raise LlmNodeError("prompt_template is required")

    target_model = _json_schema_to_pydantic_model(schema)
    prompt = _render_prompt(template, input_data)
    system_prompt = node_config.get("system_prompt", "")

    model = _build_model(provider, model_name, node_config)
    agent = Agent(model, output_type=target_model, system_prompt=system_prompt)
    try:
        result = await agent.run(prompt)
    except Exception as exc:
        raise LlmNodeError(f"structured llm call failed: {exc}") from exc

    output = result.output
    # pydantic models stringify via model_dump for JSON-safe output
    data = (
        output.model_dump()
        if hasattr(output, "model_dump")
        else dict(cast(Any, output))
    )
    return {"data": data, "usage": _extract_usage(result)}


def _json_schema_to_pydantic_model(schema: dict[str, Any]) -> type:
    """Build a pydantic BaseModel class from a JSON Schema object.

    v1 supports object/array/primitives + nullable. ``$ref`` and
    ``oneOf`` are deferred to v2 — workflows that need them can use
    the plain LLM handler with their own JSON-schema enforcement.

    The runtime class name doesn't matter (the engine only sees the
    serialised model_dump output), so we name it ``DynamicTarget``
    and trust pydantic for the rest.
    """
    from pydantic import BaseModel, Field, create_model

    if schema.get("type") != "object":
        raise LlmNodeError("schema_json must be a JSON Schema 'object' type")

    properties = schema.get("properties") or {}
    required = set(schema.get("required") or [])
    if not isinstance(properties, dict):
        raise LlmNodeError("schema_json.properties must be a dict")

    fields: dict[str, Any] = {}
    for name, sub in properties.items():
        if not isinstance(sub, dict):
            raise LlmNodeError(f"schema_json.properties.{name} must be a dict")
        py_type = _json_type_to_python(sub)
        default = ... if name in required else None
        description = sub.get("description")
        fields[name] = (
            py_type if name in required else py_type | None,
            Field(
                default,
                description=description if isinstance(description, str) else None,
            ),
        )

    return create_model("DynamicTarget", __base__=BaseModel, **fields)


def _json_type_to_python(sub: dict[str, Any]) -> Any:
    """Map a JSON Schema primitive type to a Python annotation."""
    json_type = sub.get("type")
    if json_type == "string":
        return str
    if json_type == "integer":
        return int
    if json_type == "number":
        return float
    if json_type == "boolean":
        return bool
    if json_type == "array":
        items = sub.get("items") or {}
        if not isinstance(items, dict):
            return list[Any]
        return list[_json_type_to_python(items)]  # type: ignore[misc]
    if json_type == "object":
        # Nested objects fall through to dict — building a fully-
        # typed nested model graph from JSON Schema is v2.
        return dict[str, Any]
    raise LlmNodeError(f"unsupported JSON Schema type {json_type!r}")


def _extract_usage(result: Any) -> dict[str, int]:
    """Pull usage counts from the pydantic-ai run result.

    pydantic-ai's ``.usage()`` returns an object with input/output
    token counts. Test models report zero — that's fine.
    """
    try:
        usage = result.usage()
        return {
            "input_tokens": int(getattr(usage, "input_tokens", 0) or 0),
            "output_tokens": int(getattr(usage, "output_tokens", 0) or 0),
        }
    except Exception:
        return {"input_tokens": 0, "output_tokens": 0}
