"""Loop / Map node — iterate an inner handler over an array.

A loop_map node dispatches another registered handler N times,
once per element of an input array, and collects the results.
Useful for "for each RFI in the digest, run the LLM extraction"
style flows without forcing the workflow author to draw N
parallel branches.

Scope (deliberately tight for v1):
    - Single inner node type per loop, not a sub-graph
    - Sequential execution — parallel fan-out lands in M4.3e
      (needs concurrency control + per-item error policy)
    - All-or-nothing error semantics: any inner-iteration
      failure raises and short-circuits the loop. M4.3e can
      add continue-on-error + a partial_failures output channel
      once the policy is settled.

Why a single inner node, not a sub-graph:
    Sub-graph execution needs a sub-Run abstraction so per-step
    NodeRun rows write under a parent. That refactor is M4.3f.
    For v1 the single-inner-node shape covers the most common
    workflow author intent — "fan an LLM call out across a
    list of inputs" — without changing the Run model.

``node_config`` shape:
    inner_type:   str   A registered node type (rag_search, llm,
                        http, ...). Must exist in node_registry.
    inner_config: dict  Passed straight to the inner handler.
                        ``{item}`` placeholders inside any string
                        values are rendered per-iteration.
    items_path:   str   Optional. Names the input_data key that
                        carries the iterable; defaults to
                        ``"items"``. Workflow author can wire it
                        to a previous node's output without an
                        adapter node.
    max_items:    int   Optional cap on iteration count. Default
                        100. Caps a runaway input from monopolising
                        the engine + downstream provider quota.

Output shape:
    {
        "results":   [...],  # one entry per inner-handler output
        "item_count": int,    # len(results)
    }
"""

from __future__ import annotations

from typing import Any


class LoopMapNodeError(RuntimeError):
    """Surfaces a config or runtime error in the loop handler."""


_DEFAULT_MAX_ITEMS = 100


async def loop_map_handler(
    ctx: dict[str, Any],
    node_config: dict[str, Any],
    input_data: dict[str, Any],
) -> dict[str, Any]:
    inner_type = node_config.get("inner_type")
    if not isinstance(inner_type, str) or not inner_type:
        raise LoopMapNodeError("inner_type is required")

    raw_inner_config = node_config.get("inner_config", {})
    if not isinstance(raw_inner_config, dict):
        raise LoopMapNodeError("inner_config must be a dict")

    items_path = node_config.get("items_path", "items")
    if not isinstance(items_path, str) or not items_path:
        raise LoopMapNodeError("items_path must be a non-empty string")

    raw_items = input_data.get(items_path)
    if raw_items is None:
        raise LoopMapNodeError(f"items_path {items_path!r} not present in input_data")
    if not isinstance(raw_items, (list, tuple)):
        raise LoopMapNodeError(
            f"items_path {items_path!r} must reference a list/tuple, got "
            f"{type(raw_items).__name__}"
        )

    max_items = int(node_config.get("max_items", _DEFAULT_MAX_ITEMS))
    if max_items < 1:
        raise LoopMapNodeError("max_items must be >= 1")
    if len(raw_items) > max_items:
        raise LoopMapNodeError(
            f"items_path produced {len(raw_items)} entries; max_items is {max_items}"
        )

    # Lazy import — avoids a circular at module load time
    # (node_registry imports this file's handler).
    from rapidly.agents.execution.node_registry import get_handler

    inner = get_handler(inner_type)
    if inner is None:
        raise LoopMapNodeError(
            f"inner_type {inner_type!r} is not a registered node type"
        )

    results: list[Any] = []
    for index, item in enumerate(raw_items):
        rendered = _render_config(raw_inner_config, item=item, index=index)
        iter_input = {"item": item, "index": index}
        try:
            output = await inner(ctx, rendered, iter_input)
        except Exception as exc:
            raise LoopMapNodeError(
                f"inner iteration {index} (type={inner_type!r}) failed: {exc}"
            ) from exc
        results.append(output)

    return {"results": results, "item_count": len(results)}


def _render_config(
    config: dict[str, Any],
    *,
    item: Any,
    index: int,
) -> dict[str, Any]:
    """Render ``{item}`` and ``{index}`` placeholders inside string
    values of ``config``. Non-string values pass through unchanged.

    Uses the same SafeDict-format_map pattern as the LLM handler's
    prompt renderer + the gate handler's left/right values — one
    consistent template story across the engine.
    """

    class _SafeDict(dict):  # type: ignore[type-arg]
        def __missing__(self, key: str) -> str:
            return "{" + key + "}"

    binding = _SafeDict({"item": item, "index": index})

    out: dict[str, Any] = {}
    for k, v in config.items():
        if isinstance(v, str):
            out[k] = v.format_map(binding)
        elif isinstance(v, dict):
            # One level of nested dict — supports e.g.
            # ``{"headers": {"X-Item": "{item}"}}``. Deeper
            # nesting would need a recursive walk; we keep it
            # one level for now because the existing inner
            # configs (rag_search, llm, http, gate) all use a
            # flat-with-one-nested shape.
            out[k] = {
                nk: (nv.format_map(binding) if isinstance(nv, str) else nv)
                for nk, nv in v.items()
            }
        else:
            out[k] = v
    return out
