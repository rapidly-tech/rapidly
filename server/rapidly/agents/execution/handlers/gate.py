"""Gate node — early-exit primitive for the engine's linear walk.

A gate evaluates a single comparison against input_data fields.
On success, the downstream nodes run normally. On failure, the
engine marks every downstream node as ``skipped`` and finishes
the run as ``succeeded`` — a failed gate is a "deliberate bail
out", not an error.

Why this shape and not full conditional edges:
    Full edge predicates (LangChain-style ``conditional_edge``)
    require the engine to switch from "iterate topological
    order" to "trace active edges per output". That refactor is
    M4.3c. For v1 the gate handler covers the most common
    workflow author intent — "only run the LLM if the input
    matched the filter" — without a new graph traversal mode.

Why ``raise GateFailedError`` instead of returning a flag:
    The engine already special-cases handler exceptions for
    failure reporting. Reusing that path keeps the gate's
    skip-downstream behaviour in one place (the engine catches
    the exception, walks descendants, marks them, and resumes
    the topological iteration). A flag would need a parallel
    branch in the engine's per-node loop.

``node_config`` shape:
    left:     str  Template against input_data (``"{count}"`` etc.)
    operator: str  One of ``==``, ``!=``, ``<``, ``<=``, ``>``, ``>=``, ``in``, ``not in``, ``contains``
    right:    str  Literal or template; compared as the operator's
                   right side. Numeric ops coerce both sides via
                   ``float`` before comparing; string ops compare
                   the rendered strings.

The output (on success) is ``{"passed": True, "left": ..., "right": ...}``.
"""

from __future__ import annotations

from typing import Any


class GateNodeError(RuntimeError):
    """Surfaces a config error (bad operator, missing field).
    Distinct from ``GateFailedError`` which signals a deliberate
    skip, not a misconfiguration.
    """


class GateFailedError(RuntimeError):
    """Raised when the gate's condition evaluates to False.

    The engine catches this specifically and marks every
    descendant as ``skipped`` (not ``failed``). The run completes
    as ``succeeded`` — a closed gate is normal flow control, not
    an error condition.
    """

    def __init__(self, *, left: Any, right: Any, operator: str) -> None:
        super().__init__(f"gate condition failed: {left!r} {operator} {right!r}")
        self.left = left
        self.right = right
        self.operator = operator


_NUMERIC_OPS = {"<", "<=", ">", ">="}
_EQUALITY_OPS = {"==", "!="}
_MEMBERSHIP_OPS = {"in", "not in", "contains"}


async def gate_handler(
    ctx: dict[str, Any],
    node_config: dict[str, Any],
    input_data: dict[str, Any],
) -> dict[str, Any]:
    operator = str(node_config.get("operator", "")).strip()
    if not operator:
        raise GateNodeError("operator is required")
    if (
        operator not in _NUMERIC_OPS
        and operator not in _EQUALITY_OPS
        and operator not in _MEMBERSHIP_OPS
    ):
        raise GateNodeError(
            f"unknown operator {operator!r} "
            f"(supported: ==, !=, <, <=, >, >=, in, not in, contains)"
        )

    raw_left = node_config.get("left")
    raw_right = node_config.get("right")
    if raw_left is None:
        raise GateNodeError("left is required")
    if raw_right is None:
        raise GateNodeError("right is required")

    left = _render(raw_left, input_data)
    right = _render(raw_right, input_data)

    passed = _evaluate(left=left, right=right, operator=operator)
    if not passed:
        raise GateFailedError(left=left, right=right, operator=operator)
    return {"passed": True, "left": left, "right": right}


def _render(value: Any, input_data: dict[str, Any]) -> Any:
    """Render templated config values against ``input_data``.

    A ``str`` value containing ``{key}`` is treated as a template
    and rendered with the input_data dict. Non-string values are
    passed through unchanged so a literal number or list still
    works on the right side.

    Missing keys leave the literal placeholder in place — same
    behaviour as the LLM handler's prompt renderer so workflow
    authors see one consistent template story.
    """
    if not isinstance(value, str):
        return value

    class _SafeDict(dict):  # type: ignore[type-arg]
        def __missing__(self, key: str) -> str:
            return "{" + key + "}"

    return value.format_map(_SafeDict(input_data))


def _evaluate(*, left: Any, right: Any, operator: str) -> bool:
    if operator in _EQUALITY_OPS:
        # String comparison after rendering — keeps the gate
        # predictable for non-numeric values (status strings, ids).
        passed = str(left) == str(right)
        return passed if operator == "==" else not passed
    if operator in _NUMERIC_OPS:
        try:
            l_val = float(left)
            r_val = float(right)
        except (TypeError, ValueError) as exc:
            raise GateNodeError(
                f"numeric operator {operator} needs castable values; got "
                f"left={left!r} right={right!r}"
            ) from exc
        if operator == "<":
            return l_val < r_val
        if operator == "<=":
            return l_val <= r_val
        if operator == ">":
            return l_val > r_val
        return l_val >= r_val  # operator == ">="
    # Membership: "in" / "not in" / "contains".
    #
    # ``in`` checks if left is a substring of right (string) or
    # a member of right (sequence). ``contains`` reverses that
    # — checks if right is a substring of left. Workflow authors
    # asked for both directions; the editor's "contains" affordance
    # reads more natural than "left in right" for the common case
    # of "does this body contain the keyword".
    if operator == "contains":
        return str(right) in str(left)
    # "in" / "not in" — string-or-sequence membership.
    if isinstance(right, str):
        member = str(left) in right
    elif isinstance(right, (list, tuple, set, frozenset)):
        member = left in right
    else:
        raise GateNodeError(
            f"'{operator}' needs a string or sequence right; got {type(right).__name__}"
        )
    return member if operator == "in" else not member
