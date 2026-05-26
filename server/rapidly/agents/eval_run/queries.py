"""EvalRun + EvalRunCase persistence layer."""

from uuid import UUID

from sqlalchemy import Select, select

from rapidly.core.queries import FindByIdMixin, Repository
from rapidly.identity.auth.models import (
    AuthPrincipal,
    User,
    Workspace,
    is_user_principal,
    is_workspace_principal,
)
from rapidly.models import EvalRun, EvalRunCase, WorkspaceMembership


class EvalRunRepository(
    FindByIdMixin[EvalRun, UUID],
    Repository[EvalRun],
):
    model = EvalRun

    def get_readable_statement(
        self, auth_subject: AuthPrincipal[User | Workspace]
    ) -> Select[tuple[EvalRun]]:
        statement = self.get_base_statement()
        if is_user_principal(auth_subject):
            user = auth_subject.subject
            statement = statement.where(
                EvalRun.workspace_id.in_(
                    select(WorkspaceMembership.workspace_id).where(
                        WorkspaceMembership.user_id == user.id,
                        WorkspaceMembership.deleted_at.is_(None),
                    )
                )
            )
        elif is_workspace_principal(auth_subject):
            statement = statement.where(EvalRun.workspace_id == auth_subject.subject.id)
        return statement


class EvalRunCaseRepository(
    FindByIdMixin[EvalRunCase, UUID],
    Repository[EvalRunCase],
):
    """Case rows are scoped through the parent EvalRun; the
    action layer joins through the parent to enforce auth.
    """

    model = EvalRunCase

    def for_eval_run(self, eval_run_id: UUID) -> Select[tuple[EvalRunCase]]:
        return self.get_base_statement().where(EvalRunCase.eval_run_id == eval_run_id)
