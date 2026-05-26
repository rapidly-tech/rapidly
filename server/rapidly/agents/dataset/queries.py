"""Dataset + DatasetCase persistence layer."""

from uuid import UUID

from sqlalchemy import Select, select

from rapidly.core.queries import FindByIdMixin, Repository, SoftDeleteMixin
from rapidly.identity.auth.models import (
    AuthPrincipal,
    User,
    Workspace,
    is_user_principal,
    is_workspace_principal,
)
from rapidly.models import Dataset, DatasetCase, WorkspaceMembership


class DatasetRepository(
    SoftDeleteMixin[Dataset],
    FindByIdMixin[Dataset, UUID],
    Repository[Dataset],
):
    model = Dataset

    def get_readable_statement(
        self, auth_subject: AuthPrincipal[User | Workspace]
    ) -> Select[tuple[Dataset]]:
        statement = self.get_base_statement()

        if is_user_principal(auth_subject):
            user = auth_subject.subject
            statement = statement.where(
                Dataset.workspace_id.in_(
                    select(WorkspaceMembership.workspace_id).where(
                        WorkspaceMembership.user_id == user.id,
                        WorkspaceMembership.deleted_at.is_(None),
                    )
                )
            )
        elif is_workspace_principal(auth_subject):
            statement = statement.where(Dataset.workspace_id == auth_subject.subject.id)

        return statement


class DatasetCaseRepository(
    FindByIdMixin[DatasetCase, UUID],
    Repository[DatasetCase],
):
    """Per-case repo. Tenancy is enforced via the parent dataset
    (loaded with DatasetRepository before any case access) — the
    case rows themselves don't carry workspace_id, so the readable
    statement here is just "rows for this dataset_id" and the
    action layer joins through the dataset to enforce auth.
    """

    model = DatasetCase

    def for_dataset(self, dataset_id: UUID) -> Select[tuple[DatasetCase]]:
        return self.get_base_statement().where(DatasetCase.dataset_id == dataset_id)
