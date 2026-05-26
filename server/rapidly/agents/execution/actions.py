"""Public actions for the execution engine.

The trigger endpoint calls ``start_run`` to persist a fresh Run +
dispatch the actor. The engine itself is internal to this module.
"""

from typing import Any

from rapidly.errors import NotPermitted, ResourceNotFound
from rapidly.identity.auth.models import AuthPrincipal, User, Workspace
from rapidly.models import Run, RunStatus, TriggeredByKind, Workflow
from rapidly.postgres import AsyncSession
from rapidly.worker import dispatch_task


async def start_run(
    session: AsyncSession,
    auth_subject: AuthPrincipal[User | Workspace],
    *,
    workflow: Workflow,
    input_data: dict[str, Any],
) -> Run:
    """Create a Run row in ``pending`` and dispatch the engine actor.

    Resolves the run to the workflow's ``current_version_id`` — a
    workflow with no published version surfaces a clear 412 (raised
    as NotPermitted from the API). The actor re-loads the row in
    its own session, so we just need the id persisted.
    """
    if workflow.current_version_id is None:
        # Per the strategic plan: a workflow without a published
        # version can't be run. The trigger endpoint maps this to
        # 412 Precondition Failed.
        raise NotPermitted(
            "Workflow has no published version. Publish a version before triggering."
        )

    # Resolve the triggered_by reference from the auth subject.
    if isinstance(auth_subject.subject, User):
        triggered_kind = TriggeredByKind.user
        triggered_id = auth_subject.subject.id
    elif isinstance(auth_subject.subject, Workspace):
        # Workspace-token triggers are valid (e.g. a CI integration);
        # the id is the workspace itself so the audit trail can find
        # which token group fired this.
        triggered_kind = TriggeredByKind.user  # mapped to user-like for v1
        triggered_id = auth_subject.subject.id
    else:
        raise ResourceNotFound("Cannot resolve trigger subject.")

    run = Run(
        workflow_version_id=workflow.current_version_id,
        triggered_by_kind=triggered_kind,
        triggered_by_id=triggered_id,
        status=RunStatus.pending,
        input_data=input_data,
    )
    session.add(run)
    await session.flush()
    # Dispatch only after the flush so the actor's SELECT-by-id
    # resolves.
    dispatch_task("agents.execute_run", run_id=run.id)
    return run
