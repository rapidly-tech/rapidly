"""Loop / Map node — iterate an inner handler over an array.

A loop_map node dispatches another registered handler N times,
once per element of an input array, and collects the results.
Useful for "for each RFI in the digest, run the LLM extraction"
style flows without forcing the workflow author to draw N
parallel branches.

Execution modes (M4.3e):
    - Sequential (default) — one iteration at a time. Simpler
      mental model + zero risk of overwhelming a downstream
      provider quota. Use for small N or rate-sensitive APIs.
    - Parallel — up to ``concurrency`` iterations in flight at
      once. Use for embarrassingly-parallel workloads where the
      provider can handle the burst (LLM with high RPM, internal
      services, batch indexing).

Error policy (M4.3e):
    - All-or-nothing (default) — any inner iteration failure
      raises ``LoopMapNodeError`` and short-circuits the loop.
      Use for workflows where partial results are useless
      (e.g., "all-or-nothing batch import").
    - Continue-on-error — failed iterations are captured into
      a ``failures`` list in the output; remaining iterations
      run. Use for tolerable-failure workloads (e.g., "send
      digest to each of N recipients, log the ones that
      bounced and move on").

Scope (still tight for v1):
    - Single inner node type per loop, not a sub-graph. Sub-graph
      execution lands in M4.3f.
    - Order-preserving — ``results`` is indexed by the *input
      position* of the item, even when running in parallel, so
      downstream nodes don't have to re-sort.

``node_config`` shape:
    inner_type:        str   A registered node type. Required.
    inner_config:      dict  Passed to the inner handler.
                             ``{item}`` / ``{index}`` placeholders
                             rendered per iteration.
    items_path:        str   Optional. input_data key for the
                             iterable; default "items".
    max_items:         int   Optional cap. Default 100.
    parallel:          bool  Optional. Default False (sequential).
    concurrency:       int   Optional. Default 5. Ignored when
                             parallel is False. Capped at 32 so
                             a single node can't exhaust the
                             worker's connection pool.
    continue_on_error: bool  Optional. Default False (all-or-
                             nothing). When True, failed
                             iterations land in ``failures``
                             and the loop runs to completion.

Output shape:
    {
        "results":    [output | None, ...],   # one entry per input
                                              # item; None where
                                              # continue_on_error
                                              # caught a failure
        "item_count": int,                    # len(input items)
        "failures":   [{"index": int,         # only present when
                        "error": str}, ...]    # continue_on_error
                                              # is True; empty if
                                              # everything passed
    }
"""

from __future__ import annotations

import asyncio
from typing import Any


class LoopMapNodeError(RuntimeError):
    """Surfaces a config or runtime error in the loop handler."""


_DEFAULT_MAX_ITEMS = 100
_DEFAULT_CONCURRENCY = 5
# Hard cap on the parallel knob. A workflow author asking for
# concurrency=1000 would exhaust the worker process's outbound
# connection pool and degrade every other workflow. 32 is
# generous enough for LLM batch workloads + tight enough to
# stay polite.
_MAX_CONCURRENCY = 32


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

    parallel = bool(node_config.get("parallel", False))
    continue_on_error = bool(node_config.get("continue_on_error", False))

    concurrency = int(node_config.get("concurrency", _DEFAULT_CONCURRENCY))
    if concurrency < 1:
        raise LoopMapNodeError("concurrency must be >= 1")
    if concurrency > _MAX_CONCURRENCY:
        concurrency = _MAX_CONCURRENCY

    # Allocate results upfront so order is preserved regardless
    # of completion order — downstream nodes index by position.
    results: list[Any] = [None] * len(raw_items)
    failures: list[dict[str, Any]] = []

    if parallel:
        await _run_parallel(
            inner=inner,
            inner_type=inner_type,
            ctx=ctx,
            inner_config_template=raw_inner_config,
            items=list(raw_items),
            results=results,
            failures=failures,
            concurrency=concurrency,
            continue_on_error=continue_on_error,
        )
    else:
        await _run_sequential(
            inner=inner,
            inner_type=inner_type,
            ctx=ctx,
            inner_config_template=raw_inner_config,
            items=list(raw_items),
            results=results,
            failures=failures,
            continue_on_error=continue_on_error,
        )

    return {
        "results": results,
        "item_count": len(results),
        "failures": failures,
    }


async def _run_sequential(
    *,
    inner: Any,
    inner_type: str,
    ctx: dict[str, Any],
    inner_config_template: dict[str, Any],
    items: list[Any],
    results: list[Any],
    failures: list[dict[str, Any]],
    continue_on_error: bool,
) -> None:
    for index, item in enumerate(items):
        try:
            results[index] = await _run_one(
                inner=inner,
                ctx=ctx,
                inner_config_template=inner_config_template,
                item=item,
                index=index,
            )
        except Exception as exc:
            if not continue_on_error:
                raise LoopMapNodeError(
                    f"inner iteration {index} (type={inner_type!r}) failed: {exc}"
                ) from exc
            failures.append({"index": index, "error": str(exc)[:500]})


async def _run_parallel(
    *,
    inner: Any,
    inner_type: str,
    ctx: dict[str, Any],
    inner_config_template: dict[str, Any],
    items: list[Any],
    results: list[Any],
    failures: list[dict[str, Any]],
    concurrency: int,
    continue_on_error: bool,
) -> None:
    """Fan out N iterations, capped at ``concurrency`` in flight.

    The Semaphore bounds in-flight work; ``asyncio.gather`` with
    ``return_exceptions=True`` lets us collect every result
    (success or failure) in one pass even when ``continue_on_error``
    is False — we surface the first exception after gathering so
    other iterations don't keep running for nothing once one's
    been chosen as the failure to report.
    """
    sem = asyncio.Semaphore(concurrency)

    async def _wrapped(idx: int, item_value: Any) -> tuple[int, Any]:
        async with sem:
            try:
                output = await _run_one(
                    inner=inner,
                    ctx=ctx,
                    inner_config_template=inner_config_template,
                    item=item_value,
                    index=idx,
                )
                return idx, output
            except Exception as exc:
                return idx, exc

    coros = [_wrapped(i, item) for i, item in enumerate(items)]
    gathered = await asyncio.gather(*coros)

    for index, outcome in gathered:
        if isinstance(outcome, Exception):
            if not continue_on_error:
                raise LoopMapNodeError(
                    f"inner iteration {index} (type={inner_type!r}) failed: {outcome}"
                ) from outcome
            failures.append({"index": index, "error": str(outcome)[:500]})
        else:
            results[index] = outcome


async def _run_one(
    *,
    inner: Any,
    ctx: dict[str, Any],
    inner_config_template: dict[str, Any],
    item: Any,
    index: int,
) -> dict[str, Any]:
    rendered = _render_config(inner_config_template, item=item, index=index)
    iter_input = {"item": item, "index": index}
    return await inner(ctx, rendered, iter_input)


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
