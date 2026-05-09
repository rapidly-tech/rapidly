"""Tests for member repository queries."""

import pytest

from rapidly.core.utils import now_utc
from rapidly.identity.member.queries import MemberRepository
from rapidly.models import Member, Workspace
from rapidly.models.member import MemberRole
from rapidly.postgres import AsyncSession
from tests.fixtures.database import SaveFixture
from tests.fixtures.random_objects import create_customer, create_workspace


@pytest.mark.asyncio
class TestListByEmailAndWorkspace:
    async def test_no_members_returns_empty(
        self,
        session: AsyncSession,
        workspace: Workspace,
    ) -> None:
        """Test that no matching members returns empty list."""
        repository = MemberRepository.from_session(session)

        members = await repository.list_by_email_and_workspace(
            "nonexistent@example.com", workspace.id
        )

        assert len(members) == 0

    async def test_single_member_returned(
        self,
        session: AsyncSession,
        save_fixture: SaveFixture,
        workspace: Workspace,
    ) -> None:
        """Test that single matching member is returned."""
        customer = await create_customer(
            save_fixture, workspace=workspace, email="test@example.com"
        )
        member = Member(
            customer_id=customer.id,
            workspace_id=workspace.id,
            email="test@example.com",
            name="Test User",
            role=MemberRole.owner,
        )
        await save_fixture(member)

        repository = MemberRepository.from_session(session)
        members = await repository.list_by_email_and_workspace(
            "test@example.com", workspace.id
        )

        assert len(members) == 1
        assert members[0].id == member.id
        assert members[0].email == "test@example.com"

    async def test_multiple_members_same_email_returned(
        self,
        session: AsyncSession,
        save_fixture: SaveFixture,
        workspace: Workspace,
    ) -> None:
        """Test that multiple members with same email are returned."""
        customer1 = await create_customer(
            save_fixture, workspace=workspace, email="customer1@example.com"
        )
        customer2 = await create_customer(
            save_fixture, workspace=workspace, email="customer2@example.com"
        )

        shared_email = "shared@example.com"
        member1 = Member(
            customer_id=customer1.id,
            workspace_id=workspace.id,
            email=shared_email,
            name="Member One",
            role=MemberRole.owner,
        )
        member2 = Member(
            customer_id=customer2.id,
            workspace_id=workspace.id,
            email=shared_email,
            name="Member Two",
            role=MemberRole.member,
        )
        await save_fixture(member1)
        await save_fixture(member2)

        repository = MemberRepository.from_session(session)
        members = await repository.list_by_email_and_workspace(
            shared_email, workspace.id
        )

        assert len(members) == 2
        member_ids = {m.id for m in members}
        assert member1.id in member_ids
        assert member2.id in member_ids

    async def test_case_insensitive_email(
        self,
        session: AsyncSession,
        save_fixture: SaveFixture,
        workspace: Workspace,
    ) -> None:
        """Test that email matching is case-insensitive."""
        customer = await create_customer(
            save_fixture, workspace=workspace, email="user@example.com"
        )
        member = Member(
            customer_id=customer.id,
            workspace_id=workspace.id,
            email="user@example.com",
            role=MemberRole.owner,
        )
        await save_fixture(member)

        repository = MemberRepository.from_session(session)

        # Test uppercase
        members_upper = await repository.list_by_email_and_workspace(
            "USER@EXAMPLE.COM", workspace.id
        )
        assert len(members_upper) == 1
        assert members_upper[0].id == member.id

        # Test mixed case
        members_mixed = await repository.list_by_email_and_workspace(
            "User@Example.Com", workspace.id
        )
        assert len(members_mixed) == 1
        assert members_mixed[0].id == member.id

    async def test_excludes_soft_deleted_members(
        self,
        session: AsyncSession,
        save_fixture: SaveFixture,
        workspace: Workspace,
    ) -> None:
        """Test that soft-deleted members are excluded."""
        customer = await create_customer(
            save_fixture, workspace=workspace, email="deleted@example.com"
        )
        member = Member(
            customer_id=customer.id,
            workspace_id=workspace.id,
            email="deleted@example.com",
            role=MemberRole.owner,
            deleted_at=now_utc(),  # Soft-deleted
        )
        await save_fixture(member)

        repository = MemberRepository.from_session(session)
        members = await repository.list_by_email_and_workspace(
            "deleted@example.com", workspace.id
        )

        assert len(members) == 0

    async def test_filters_by_workspace(
        self,
        session: AsyncSession,
        save_fixture: SaveFixture,
        workspace: Workspace,
    ) -> None:
        """Test that only members from specified workspace are returned."""
        # Create member in primary workspace
        customer1 = await create_customer(
            save_fixture, workspace=workspace, email="customer1@example.com"
        )
        member1 = Member(
            customer_id=customer1.id,
            workspace_id=workspace.id,
            email="shared@example.com",
            role=MemberRole.owner,
        )
        await save_fixture(member1)

        # Create member with same email in different workspace
        other_org = await create_workspace(save_fixture)
        customer2 = await create_customer(
            save_fixture, workspace=other_org, email="customer2@example.com"
        )
        member2 = Member(
            customer_id=customer2.id,
            workspace_id=other_org.id,
            email="shared@example.com",
            role=MemberRole.owner,
        )
        await save_fixture(member2)

        repository = MemberRepository.from_session(session)

        # Query primary workspace
        members_org1 = await repository.list_by_email_and_workspace(
            "shared@example.com", workspace.id
        )
        assert len(members_org1) == 1
        assert members_org1[0].id == member1.id

        # Query other workspace
        members_org2 = await repository.list_by_email_and_workspace(
            "shared@example.com", other_org.id
        )
        assert len(members_org2) == 1
        assert members_org2[0].id == member2.id

    async def test_eager_loads_customer(
        self,
        session: AsyncSession,
        save_fixture: SaveFixture,
        workspace: Workspace,
    ) -> None:
        """Test that customer relationship is eagerly loaded."""
        customer = await create_customer(
            save_fixture,
            workspace=workspace,
            email="test@example.com",
            name="Test Customer",
        )
        member = Member(
            customer_id=customer.id,
            workspace_id=workspace.id,
            email="test@example.com",
            role=MemberRole.owner,
        )
        await save_fixture(member)

        repository = MemberRepository.from_session(session)
        members = await repository.list_by_email_and_workspace(
            "test@example.com", workspace.id
        )

        assert len(members) == 1
        # Access customer without additional query (eager loaded)
        assert members[0].customer.id == customer.id
        assert members[0].customer.name == "Test Customer"
