"""Tests for the Dataset + DatasetCase actions."""

from __future__ import annotations

import uuid

import pytest

from rapidly.agents.dataset import actions
from rapidly.agents.dataset.types import (
    DatasetCaseCreate,
    DatasetCaseUpdate,
    DatasetCreate,
    DatasetUpdate,
)
from rapidly.core.pagination import PaginationParams
from rapidly.errors import ResourceNotFound
from rapidly.identity.auth.models import AuthPrincipal
from rapidly.models import Dataset, User, Workspace, WorkspaceMembership
from rapidly.postgres import AsyncSession


async def _member_principal(
    session: AsyncSession, workspace: Workspace
) -> AuthPrincipal[User]:
    user = User(email=f"u-{uuid.uuid4().hex[:6]}@example.com")
    session.add(user)
    await session.flush()
    session.add(WorkspaceMembership(user_id=user.id, workspace_id=workspace.id))
    await session.flush()
    return AuthPrincipal(subject=user, scopes=set(), session=None)


@pytest.mark.asyncio
class TestCreateDataset:
    async def test_persists_with_workspace_check(
        self,
        session: AsyncSession,
        workspace: Workspace,
    ) -> None:
        principal = await _member_principal(session, workspace)
        dataset = await actions.create_dataset(
            session,
            principal,
            DatasetCreate(
                workspace_id=workspace.id,
                name="rfi-triage-v1",
                description="Golden set for the RFI triage workflow.",
            ),
        )
        assert dataset.workspace_id == workspace.id
        assert dataset.name == "rfi-triage-v1"
        assert dataset.description.startswith("Golden")

    async def test_user_without_membership_rejected(
        self,
        session: AsyncSession,
        workspace: Workspace,
    ) -> None:
        # User exists but isn't a member of the workspace.
        user = User(email=f"u-{uuid.uuid4().hex[:6]}@example.com")
        session.add(user)
        await session.flush()
        principal = AuthPrincipal(subject=user, scopes=set(), session=None)

        with pytest.raises(ResourceNotFound):
            await actions.create_dataset(
                session,
                principal,
                DatasetCreate(workspace_id=workspace.id, name="x"),
            )


@pytest.mark.asyncio
class TestListAndGet:
    async def test_other_workspace_datasets_not_visible(
        self,
        session: AsyncSession,
        workspace: Workspace,
    ) -> None:
        # Caller belongs to ``workspace``; another workspace has
        # its own dataset. Must not appear in the caller's list.
        principal = await _member_principal(session, workspace)
        own = await actions.create_dataset(
            session,
            principal,
            DatasetCreate(workspace_id=workspace.id, name="own"),
        )

        slug = f"o-{uuid.uuid4().hex[:6]}"
        other_ws = Workspace(name=slug, slug=slug, customer_invoice_prefix=slug.upper())
        session.add(other_ws)
        await session.flush()
        other_dataset = Dataset(workspace_id=other_ws.id, name="other")
        session.add(other_dataset)
        await session.flush()

        rows, count = await actions.list_datasets(
            session, principal, pagination=PaginationParams(limit=50, page=1)
        )
        assert count == 1
        assert rows[0].id == own.id

        # And direct get on the other-workspace dataset is 404.
        with pytest.raises(ResourceNotFound):
            await actions.get_dataset_or_raise(session, principal, other_dataset.id)

    async def test_name_filter_substring_match(
        self,
        session: AsyncSession,
        workspace: Workspace,
    ) -> None:
        # Real-DB substring match: name is case-insensitive,
        # internal whitespace + casing differences must not break
        # the match, and SQL wildcards in the input must be
        # treated as literals.
        principal = await _member_principal(session, workspace)
        await actions.create_dataset(
            session,
            principal,
            DatasetCreate(workspace_id=workspace.id, name="rfi-triage"),
        )
        await actions.create_dataset(
            session,
            principal,
            DatasetCreate(workspace_id=workspace.id, name="rfi_other"),
        )
        await actions.create_dataset(
            session,
            principal,
            DatasetCreate(workspace_id=workspace.id, name="unrelated"),
        )

        rows, count = await actions.list_datasets(
            session,
            principal,
            name="RFI",
            pagination=PaginationParams(limit=50, page=1),
        )
        # Case-insensitive substring catches both rfi-* datasets.
        assert count == 2
        names = sorted(r.name for r in rows)
        assert names == ["rfi-triage", "rfi_other"]

        # ``_`` in the input must be treated as a literal, not a
        # SQL single-char wildcard — so "rfi_" should match only
        # the literal-underscore row.
        rows, count = await actions.list_datasets(
            session,
            principal,
            name="rfi_",
            pagination=PaginationParams(limit=50, page=1),
        )
        assert count == 1
        assert rows[0].name == "rfi_other"

        # Whitespace-only input is treated as "no filter".
        rows, count = await actions.list_datasets(
            session,
            principal,
            name="   ",
            pagination=PaginationParams(limit=50, page=1),
        )
        assert count == 3


@pytest.mark.asyncio
class TestUpdateDataset:
    async def test_empty_payload_noop(
        self,
        session: AsyncSession,
        workspace: Workspace,
    ) -> None:
        principal = await _member_principal(session, workspace)
        dataset = await actions.create_dataset(
            session,
            principal,
            DatasetCreate(workspace_id=workspace.id, name="orig"),
        )
        result = await actions.update_dataset(
            session, principal, dataset, DatasetUpdate()
        )
        assert result is dataset
        assert dataset.name == "orig"

    async def test_partial_update_persists(
        self,
        session: AsyncSession,
        workspace: Workspace,
    ) -> None:
        principal = await _member_principal(session, workspace)
        dataset = await actions.create_dataset(
            session,
            principal,
            DatasetCreate(workspace_id=workspace.id, name="orig"),
        )
        await actions.update_dataset(
            session,
            principal,
            dataset,
            DatasetUpdate(name="renamed"),
        )
        await session.refresh(dataset)
        assert dataset.name == "renamed"


@pytest.mark.asyncio
class TestDeleteDataset:
    async def test_soft_deletes(
        self,
        session: AsyncSession,
        workspace: Workspace,
    ) -> None:
        principal = await _member_principal(session, workspace)
        dataset = await actions.create_dataset(
            session,
            principal,
            DatasetCreate(workspace_id=workspace.id, name="to-delete"),
        )
        await actions.delete_dataset(session, principal, dataset)
        await session.refresh(dataset)
        assert dataset.deleted_at is not None

        # Subsequent get returns 404 (soft-deleted rows are
        # filtered by SoftDeleteMixin.get_base_statement).
        with pytest.raises(ResourceNotFound):
            await actions.get_dataset_or_raise(session, principal, dataset.id)


@pytest.mark.asyncio
class TestCaseLifecycle:
    async def test_create_list_update_delete(
        self,
        session: AsyncSession,
        workspace: Workspace,
    ) -> None:
        principal = await _member_principal(session, workspace)
        dataset = await actions.create_dataset(
            session,
            principal,
            DatasetCreate(workspace_id=workspace.id, name="rfi"),
        )

        # Create two cases at different order_index values to
        # verify ordering.
        case_a = await actions.create_case(
            session,
            dataset,
            DatasetCaseCreate(
                name="case-a",
                input_data={"text": "concrete spec"},
                expected_output={"label": "spec"},
                order_index=1,
            ),
        )
        case_b = await actions.create_case(
            session,
            dataset,
            DatasetCaseCreate(
                name="case-b",
                input_data={"text": "empty submittal"},
                # expected_output omitted — qualitative review
                order_index=0,
            ),
        )

        # List returns them in order_index ASC.
        rows = await actions.list_cases(session, principal, dataset)
        assert [r.id for r in rows] == [case_b.id, case_a.id]
        assert rows[0].expected_output is None

        # Update one
        await actions.update_case(
            session, case_a, DatasetCaseUpdate(name="case-a-renamed")
        )
        await session.refresh(case_a)
        assert case_a.name == "case-a-renamed"

        # Delete (hard delete — see actions.py comment)
        await actions.delete_case(session, case_b)
        rows = await actions.list_cases(session, principal, dataset)
        assert [r.id for r in rows] == [case_a.id]

    async def test_get_case_or_raise_404_cross_dataset(
        self,
        session: AsyncSession,
        workspace: Workspace,
    ) -> None:
        # Case belongs to dataset_a; get_case_or_raise against
        # dataset_b returns 404 (defense in depth — the API
        # surface verifies the case belongs to the dataset_id
        # in the URL, not just that the caller can read both).
        principal = await _member_principal(session, workspace)
        dataset_a = await actions.create_dataset(
            session, principal, DatasetCreate(workspace_id=workspace.id, name="a")
        )
        dataset_b = await actions.create_dataset(
            session, principal, DatasetCreate(workspace_id=workspace.id, name="b")
        )
        case = await actions.create_case(
            session,
            dataset_a,
            DatasetCaseCreate(name="c", input_data={"x": 1}),
        )

        with pytest.raises(ResourceNotFound):
            await actions.get_case_or_raise(session, dataset_b, case.id)
