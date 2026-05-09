"""Admin panel task-management routes (HTMX).

Provides a server-rendered view for browsing registered Dramatiq actors,
manually dispatching tasks, and (eventually) inspecting execution history.
"""

from collections.abc import Sequence
from operator import attrgetter
from typing import Any

from fastapi import APIRouter, Query, Request
from pydantic import ValidationError
from tagflow import tag, text

from rapidly.worker import dispatch_task

from ..components import button, datatable, input, modal
from ..layout import layout
from ..toast import add_toast
from .forms import build_enqueue_task_form_class

router = APIRouter()

# ---------------------------------------------------------------------------
# Task list
# ---------------------------------------------------------------------------


_TABLE_COLUMNS: tuple[Any, ...] = (
    datatable.DatatableDateTimeColumn("enqueue_time", "Enqueue Time"),
    datatable.DatatableDateTimeColumn("start_time", "Start Time"),
    datatable.DatatableAttrColumn("function", "Name", clipboard=True),
    datatable.DatatableAttrColumn("job_try", "Try"),
    datatable.DatatableBooleanColumn("success", "Success"),
)


@router.get("/", name="tasks:list")
async def list(
    request: Request,
    query: str | None = Query(None),
) -> None:
    items: Sequence[Any] = []
    if query:
        # Future: scan Redis for matching job results
        items = sorted(items, key=attrgetter("enqueue_time"), reverse=True)

    with layout(
        request,
        [("Tasks", str(request.url_for("tasks:list")))],
        "tasks:list",
    ):
        with tag.div(classes="flex flex-col gap-4"):
            with tag.h1(classes="text-4xl"):
                text("Tasks")
            with tag.div(classes="w-full flex flex-row justify-between"):
                with tag.form(method="GET"):
                    with input.search("query", query):
                        pass
                with button(
                    variant="primary",
                    hx_get=str(request.url_for("tasks:enqueue")),
                    hx_target="#modal",
                ):
                    text("Enqueue Task")

            with datatable.Datatable[Any, Any](
                *_TABLE_COLUMNS,
                empty_message="Enter a query to find tasks" if not query else None,
            ).render(request, items):
                pass


# ---------------------------------------------------------------------------
# Enqueue action
# ---------------------------------------------------------------------------


@router.api_route("/enqueue", name="tasks:enqueue", methods=["GET", "POST"])
async def enqueue(request: Request, task: str | None = Query(None)) -> Any:
    form_cls = build_enqueue_task_form_class(request, task)
    form_error: ValidationError | None = None

    if request.method == "POST":
        raw = await request.form()
        try:
            payload = form_cls.model_validate_form(raw)
            dispatch_task(
                payload.task,
                **payload.model_dump(exclude={"task"}),
            )
            await add_toast(request, "Task has been enqueued.", "success")
            return
        except ValidationError as exc:
            form_error = exc

    with modal("Enqueue task", open=True):
        with form_cls.render(
            {"task": task},
            method="POST",
            classes="flex flex-col",
            validation_error=form_error,
        ):
            with tag.div(classes="modal-action"):
                with tag.form(method="dialog"):
                    with button(ghost=True):
                        text("Cancel")
                with button(
                    type="button",
                    variant="primary",
                    hx_post=str(request.url),
                    hx_target="#modal",
                ):
                    text("Enqueue")
