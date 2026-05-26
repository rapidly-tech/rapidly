"""Per-node-type handler registry.

Adding a node type to the runtime = adding a file under
``handlers/`` that defines a function with the ``NodeHandler``
shape + registering it here. The engine looks up the handler by
the node's ``type`` string at execution time; unknown types fail
the NodeRun with a clear error rather than crashing the actor.

Why functions, not classes: every existing handler we'd write is
stateless (pure-ish input → output). A function fits the shape
better than a class with a single ``execute`` method.

Why a module-level dict, not a decorator: the decorator pattern
is cute but registers at import time, which makes ordering
matter. A dict is explicit and the registration site (this
module) is the single source of truth.
"""

from collections.abc import Awaitable, Callable
from typing import Any

from rapidly.agents.execution.handlers.echo import echo_handler

# A NodeHandler receives the run's context + the node's config +
# its input_data, returns its output_data. Failures raise.
#
# The ``ctx`` argument is intentionally opaque dict-typed for v1.
# When the catalog grows (HTTP node needs an httpx client, LLM
# node needs the pydantic-ai agent factory, etc.), the ctx shape
# is what carries those handles in.
NodeHandler = Callable[
    [dict[str, Any], dict[str, Any], dict[str, Any]],
    Awaitable[dict[str, Any]],
]


_REGISTRY: dict[str, NodeHandler] = {
    # Echo: copies input straight to output. Exists so the engine's
    # graph-walk can be exercised end-to-end before the real node
    # catalog (M4.3) lands.
    "echo": echo_handler,
}


def get_handler(node_type: str) -> NodeHandler | None:
    """Return the handler for ``node_type`` or None if unknown."""
    return _REGISTRY.get(node_type)


def registered_types() -> list[str]:
    """Snapshot of all currently-registered node types. Useful for
    tests and the future ``GET /api/v1/agents/node-types`` endpoint."""
    return sorted(_REGISTRY.keys())
