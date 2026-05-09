"""Dynamic HTML form generation for admin task dispatch.

Introspects Dramatiq actor signatures to build typed form fields so
that admins can manually trigger background tasks with proper arguments.
"""

import inspect
from collections.abc import Callable, Iterator
from typing import (
    Annotated,
    Any,
    Literal,
    Unpack,
    get_args,
    get_origin,
    get_type_hints,
    is_typeddict,
)

import dramatiq
from fastapi import Request
from pydantic import Field, create_model

from rapidly import workers  # noqa

from .. import forms

# ---------------------------------------------------------------------------
# Actor registry — populated once at import time
# ---------------------------------------------------------------------------

_TASK_DEFINITIONS: dict[str, dramatiq.Actor[Any, Any]] = {
    name: actor for name, actor in dramatiq.get_broker().actors.items()
}
_SORTED_TASK_NAMES: list[str] = sorted(_TASK_DEFINITIONS)
_TaskName = Literal[tuple(_TASK_DEFINITIONS.keys())]  # type: ignore[valid-type]

# Parameters that are injected by the framework, not the user.
_FRAMEWORK_PARAMS: frozenset[str] = frozenset({"self"})


# ---------------------------------------------------------------------------
# Argument introspection
# ---------------------------------------------------------------------------


def _iter_callable_params(
    fn: Callable[..., Any],
) -> Iterator[tuple[str, Any]]:
    """Yield ``(name, annotation)`` pairs for user-visible parameters of *fn*."""
    sig = inspect.signature(fn)
    for param_name, param in sig.parameters.items():
        if param_name in _FRAMEWORK_PARAMS:
            continue
        hint = param.annotation
        if get_origin(hint) is Unpack:
            inner_args = get_args(hint)
            if is_typeddict(inner_args[0]):
                yield from get_type_hints(inner_args[0]).items()
                return
            elif issubclass(inner_args[0], dict):
                yield from _iter_callable_params(inner_args[0].__init__)
                return
        yield param_name, hint


def _select_choices() -> list[tuple[str, str]]:
    return [(n, n) for n in _SORTED_TASK_NAMES]


# ---------------------------------------------------------------------------
# Form building
# ---------------------------------------------------------------------------


class EnqueueTaskFormBase(forms.BaseForm):
    task: str


def build_enqueue_task_form_class(
    request: Request, task: str | None
) -> type[EnqueueTaskFormBase]:
    """Return a dynamically-constructed Pydantic form model.

    When *task* is ``None`` the form only contains the task selector;
    once a task is chosen, extra fields matching its signature are added.
    """
    fields: dict[str, tuple[type, Any]] = {
        "task": (
            Annotated[
                _TaskName,  # type: ignore
                forms.SelectField(
                    _select_choices(),
                    hx_get=str(request.url_for("tasks:enqueue")),
                    hx_trigger="change",
                    hx_target="#modal",
                ),
                Field(title="Task"),
            ],
            ...,
        ),
    }

    if task is not None:
        actor_ref = _TASK_DEFINITIONS[task]
        for param_name, type_hint in _iter_callable_params(actor_ref.fn):
            default: Any = False if type_hint is bool else ...
            fields[param_name] = (type_hint, default)

    return create_model(
        "EnqueueTaskForm",
        **fields,  # type: ignore
        __base__=forms.BaseForm,
    )
