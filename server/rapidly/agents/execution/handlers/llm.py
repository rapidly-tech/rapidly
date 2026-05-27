"""LLM + structured-output node handlers.

Both handlers route through pydantic-ai for provider abstraction
+ structured-output via target-pydantic-model. The provider/model
combination is picked at runtime from the node config so a single
workflow can mix providers across nodes.

Credential resolution order (M4.7b):
    1. ``node_config.api_key`` — explicit override, wins over all
    2. ``IntegrationCredential`` for ``(ctx.workspace_id,
       provider)`` looked up via ``resolve_for_workspace``
    3. ``OPENAI_API_KEY`` / ``ANTHROPIC_API_KEY`` /
       ``GOOGLE_API_KEY`` env var — fallback for dev / unit tests
       and contexts without an engine-supplied session

When ``credential_id`` is present in node_config the lookup pins
to that specific row (still scoped to the workspace).

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
from uuid import UUID

from pydantic_ai import Agent

# Lazy provider imports happen inside ``_build_model``. Keeping
# them out of module scope means the test path doesn't pay the
# anthropic/google imports.


class LlmNodeError(RuntimeError):
    """Surfaces to the engine's per-node failure path."""


_ENV_VAR_BY_PROVIDER = {
    "openai": "OPENAI_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
    "google": "GOOGLE_API_KEY",
    # Ollama uses the OpenAI-compatible client; the env-var
    # fallback shares the openai slot (operators typically point
    # it at a local key or leave it unset for unauthenticated
    # Ollama instances).
    "ollama": "OPENAI_API_KEY",
}


async def _resolve_credential(
    provider: str,
    node_config: dict[str, Any],
    ctx: dict[str, Any],
) -> tuple[str | None, str | None]:
    """Pick the API key + base URL for ``provider``.

    Priority order:
        1. ``node_config["api_key"]`` if non-empty
        2. ``IntegrationCredential`` looked up via the engine's
           session + workspace_id (when both are in ctx). A
           ``credential_id`` in node_config pins the lookup;
           otherwise the workspace's default credential for
           ``provider`` is used.
        3. ``{PROVIDER}_API_KEY`` env var

    Returns ``(api_key_or_None, base_url_or_None)``. The base_url
    only comes from the credential row in path 2 — paths 1 and 3
    return ``None`` for it. The handler still consults
    ``node_config["base_url"]`` as the highest-priority override.

    Side effect: when the lookup hits the credential store, the
    matched credential's id is stuffed into ``ctx`` under
    ``_resolved_credential_id`` so the usage-tracking writer
    knows which credential to attribute the call to. The
    leading underscore signals "engine internal" — handlers
    should treat ctx fields starting with ``_`` as opaque.
    """
    raw = node_config.get("api_key")
    if isinstance(raw, str) and raw:
        return raw, None

    session = ctx.get("session")
    workspace_id = ctx.get("workspace_id")
    if session is not None and workspace_id is not None:
        from rapidly.agents.integration_credential.queries import (
            resolve_for_workspace_with_id,
        )

        ws_uuid = (
            workspace_id if isinstance(workspace_id, UUID) else UUID(str(workspace_id))
        )
        credential_id_raw = node_config.get("credential_id")
        cred_uuid: UUID | None = None
        if credential_id_raw is not None:
            cred_uuid = (
                credential_id_raw
                if isinstance(credential_id_raw, UUID)
                else UUID(str(credential_id_raw))
            )
        hit = await resolve_for_workspace_with_id(
            session,
            workspace_id=ws_uuid,
            provider=provider,
            credential_id=cred_uuid,
        )
        if hit is not None:
            resolved_id, secret, base_url = hit
            ctx["_resolved_credential_id"] = resolved_id
            return secret, base_url

    env_var = _ENV_VAR_BY_PROVIDER.get(provider)
    if env_var is None:
        return None, None
    return os.environ.get(env_var), None


async def _build_model(
    provider: str,
    model: str,
    node_config: dict[str, Any],
    ctx: dict[str, Any],
) -> Any:
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

        api_key, cred_base_url = await _resolve_credential(provider, node_config, ctx)
        # node_config.base_url wins over credential.base_url — a
        # workflow that explicitly points at, say, a private LLM
        # proxy shouldn't get overridden by what's set on the
        # default credential.
        node_base_url = node_config.get("base_url")
        base_url = (
            node_base_url
            if isinstance(node_base_url, str) and node_base_url
            else cred_base_url
        )
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
        api_key, _ = await _resolve_credential(provider, node_config, ctx)
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
        api_key, _ = await _resolve_credential(provider, node_config, ctx)
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

    model = await _build_model(provider, model_name, node_config, ctx)
    agent: Agent[None, str] = Agent(model, system_prompt=system_prompt)
    try:
        result = await agent.run(prompt)
    except Exception as exc:
        raise LlmNodeError(f"llm call failed: {exc}") from exc

    output = result.output
    usage = _extract_usage(result)
    await _record_usage(ctx=ctx, provider=provider, model=model_name, usage=usage)
    return {
        "text": output if isinstance(output, str) else str(output),
        "usage": usage,
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

    model = await _build_model(provider, model_name, node_config, ctx)
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
    usage = _extract_usage(result)
    await _record_usage(ctx=ctx, provider=provider, model=model_name, usage=usage)
    return {"data": data, "usage": usage}


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


async def _record_usage(
    *,
    ctx: dict[str, Any],
    provider: str,
    model: str,
    usage: dict[str, int],
) -> None:
    """Insert an ``LlmUsage`` row attributing this call's tokens.

    Best-effort: if the engine isn't supplying a session
    (handler invoked outside a Run, like a future eval/smoke
    test), we skip the write rather than crash. The provider
    call already succeeded by the time we reach here — losing
    a usage row is annoying but shouldn't fail the workflow.

    ``credential_id`` is the credential the resolver matched
    (stashed in ctx by ``_resolve_credential``); ``None`` for
    env-fallback or explicit-key calls.
    """
    session = ctx.get("session")
    workspace_id = ctx.get("workspace_id")
    if session is None or workspace_id is None:
        return

    from rapidly.models import LlmUsage

    ws_uuid = (
        workspace_id if isinstance(workspace_id, UUID) else UUID(str(workspace_id))
    )

    cred_id = ctx.get("_resolved_credential_id")
    cred_uuid: UUID | None = None
    if cred_id is not None:
        cred_uuid = cred_id if isinstance(cred_id, UUID) else UUID(str(cred_id))

    run_id_raw = ctx.get("run_id")
    run_uuid: UUID | None = None
    if run_id_raw is not None:
        run_uuid = run_id_raw if isinstance(run_id_raw, UUID) else UUID(str(run_id_raw))

    node_run_id_raw = ctx.get("node_run_id")
    node_run_uuid: UUID | None = None
    if node_run_id_raw is not None:
        node_run_uuid = (
            node_run_id_raw
            if isinstance(node_run_id_raw, UUID)
            else UUID(str(node_run_id_raw))
        )

    record = LlmUsage(
        workspace_id=ws_uuid,
        credential_id=cred_uuid,
        run_id=run_uuid,
        node_run_id=node_run_uuid,
        provider=provider,
        model=model,
        input_tokens=int(usage.get("input_tokens", 0) or 0),
        output_tokens=int(usage.get("output_tokens", 0) or 0),
    )
    session.add(record)
    await session.flush()

    # M4.7h: arm the budget alert if this write tipped the
    # credential's MTD past its configured threshold. No-op
    # when there's no credential (env-fallback call) or no
    # threshold configured.
    if cred_uuid is not None:
        from rapidly.agents.integration_credential.queries import (
            check_and_arm_budget_alert,
        )

        await check_and_arm_budget_alert(session, credential_id=cred_uuid)
