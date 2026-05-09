"""Ephemeral toast notifications for the Rapidly admin panel.

Toasts are accumulated on the ASGI request scope during handler
execution, then flushed into an OOB-swapped ``<div id="toast">``
container just before the response body is rendered.

Public API:

* :func:`add_toast` -- queue a message during request handling.
* :func:`render_toasts` -- emit queued toasts into the HTML tree.
"""

import contextlib
import dataclasses
from collections.abc import Generator
from typing import Literal

from fastapi import Request
from starlette.types import Scope
from tagflow import tag, text

from .components import alert

ToastLevel = Literal["info", "success", "warning", "error"]

_SCOPE_KEY = "toasts"


@dataclasses.dataclass(slots=True)
class Toast:
    """A single pending notification."""

    message: str
    variant: ToastLevel


@contextlib.contextmanager
def render_toasts(scope: Scope) -> Generator[None]:
    """Write all queued toasts into an OOB-swapped container element.

    Each toast auto-dismisses after five seconds or when clicked.
    """
    pending: list[Toast] = scope.get(_SCOPE_KEY, [])
    with tag.div(
        id="toast", classes="toast toast-bottom toast-end", hx_swap_oob="beforeend"
    ):
        for item in pending:
            _hyperscript = "init wait 5s remove me end on click remove me"
            with alert(item.variant, _=_hyperscript):
                text(item.message)
    yield


async def add_toast(
    request: Request, message: str, variant: ToastLevel = "info"
) -> None:
    """Enqueue a toast notification that will be rendered with the response."""
    queue: list[Toast] = request.scope.setdefault(_SCOPE_KEY, [])
    queue.append(Toast(message=message, variant=variant))


__all__ = ["add_toast", "render_toasts"]
