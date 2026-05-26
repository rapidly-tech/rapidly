"""Echo node handler. Copies input → output verbatim.

This handler exists so the engine's graph walk is exercisable
end-to-end before the real node catalog (M4.3) lands. Building a
two-node echo chain through the trigger endpoint should produce a
NodeRun row per node with matching input/output.
"""

from typing import Any


async def echo_handler(
    ctx: dict[str, Any],
    node_config: dict[str, Any],
    input_data: dict[str, Any],
) -> dict[str, Any]:
    """Return the input dict unchanged.

    ``ctx`` is unused (echo is stateless + has no external
    dependencies). ``node_config`` is unused; the editor doesn't
    surface config for the echo node yet.
    """
    return dict(input_data)
