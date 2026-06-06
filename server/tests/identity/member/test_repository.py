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


@pytest.mark.asyncio
class TestFindCaseInsensitiveEmailDuplicates:
    """Pre-flight check for the case-insensitive unique constraint
    migration (queued). Operators run this to surface
    (customer_id, lower(email)) groups with >1 active members
    that would block the constraint creation.

    Four load-bearing properties pinned:

    - Active-only — soft-deleted members don't count toward
      the unique constraint, so they don't need to surface.
    - Case-insensitive — that's the whole point; ``Alice@x.com``
      and ``alice@x.com`` MUST collapse into one group.
    - Per-(customer_id, email) — two members of DIFFERENT
      customers with the same email aren't duplicates (members
      are scoped per customer).
    - Returns the COUNT so operators know how many duplicates
      to merge per group.
    """

    async def test_no_duplicates_returns_empty(
        self,
        session: AsyncSession,
        save_fixture: SaveFixture,
        workspace: Workspace,
    ) -> None:
        customer = await create_customer(
            save_fixture, workspace=workspace, email="solo@example.com"
        )
        await save_fixture(
            Member(
                customer_id=customer.id,
                workspace_id=workspace.id,
                email="solo@example.com",
                role=MemberRole.owner,
            )
        )

        repo = MemberRepository.from_session(session)
        duplicates = await repo.find_case_insensitive_email_duplicates()
        assert duplicates == []

    async def test_finds_case_insensitive_duplicates(
        self,
        session: AsyncSession,
        save_fixture: SaveFixture,
        workspace: Workspace,
    ) -> None:
        customer = await create_customer(
            save_fixture, workspace=workspace, email="primary@example.com"
        )
        # Two members differing only in email case — these would
        # collide under the case-insensitive unique constraint.
        await save_fixture(
            Member(
                customer_id=customer.id,
                workspace_id=workspace.id,
                email="John@example.com",
                role=MemberRole.owner,
            )
        )
        await save_fixture(
            Member(
                customer_id=customer.id,
                workspace_id=workspace.id,
                email="john@example.com",
                role=MemberRole.member,
            )
        )

        repo = MemberRepository.from_session(session)
        duplicates = await repo.find_case_insensitive_email_duplicates()

        assert len(duplicates) == 1
        cid, lower_email, count = duplicates[0]
        assert cid == customer.id
        assert lower_email == "john@example.com"
        assert count == 2

    async def test_excludes_soft_deleted_members(
        self,
        session: AsyncSession,
        save_fixture: SaveFixture,
        workspace: Workspace,
    ) -> None:
        # Soft-deleted members shouldn't count — they don't
        # block the unique constraint (the constraint applies
        # to active rows).
        customer = await create_customer(
            save_fixture, workspace=workspace, email="x@example.com"
        )
        active = Member(
            customer_id=customer.id,
            workspace_id=workspace.id,
            email="alice@example.com",
            role=MemberRole.owner,
        )
        deleted = Member(
            customer_id=customer.id,
            workspace_id=workspace.id,
            email="ALICE@example.com",
            role=MemberRole.member,
            deleted_at=now_utc(),
        )
        await save_fixture(active)
        await save_fixture(deleted)

        repo = MemberRepository.from_session(session)
        duplicates = await repo.find_case_insensitive_email_duplicates()
        # Only one active row → no duplicate group.
        assert duplicates == []

    async def test_distinct_customers_not_grouped(
        self,
        session: AsyncSession,
        save_fixture: SaveFixture,
        workspace: Workspace,
    ) -> None:
        # Members are scoped per customer; two members at
        # different customers with the same email are NOT
        # duplicates under the (customer_id, email) unique key.
        customer_a = await create_customer(
            save_fixture, workspace=workspace, email="a@example.com"
        )
        customer_b = await create_customer(
            save_fixture, workspace=workspace, email="b@example.com"
        )
        await save_fixture(
            Member(
                customer_id=customer_a.id,
                workspace_id=workspace.id,
                email="shared@example.com",
                role=MemberRole.owner,
            )
        )
        await save_fixture(
            Member(
                customer_id=customer_b.id,
                workspace_id=workspace.id,
                email="shared@example.com",
                role=MemberRole.owner,
            )
        )

        repo = MemberRepository.from_session(session)
        duplicates = await repo.find_case_insensitive_email_duplicates()
        assert duplicates == []


@pytest.mark.asyncio
class TestListDuplicatesForDedupe:
    """Loader for a single duplicate group, ordered by the
    auto-dedupe policy: highest role first (owner >
    billing_manager > member), tie-broken by earliest
    created_at. Survivor = first row; losers = rest.

    Role is stored as a string but the natural ordering for
    picking the SURVIVOR is the enum's intent (owner >
    billing_manager > member). Alphabetically that's
    billing_manager < member < owner — would pick the WRONG
    winner. The CASE expression in the query pins the correct
    enum ordering.
    """

    async def test_owner_wins_over_lower_roles(
        self,
        session: AsyncSession,
        save_fixture: SaveFixture,
        workspace: Workspace,
    ) -> None:
        customer = await create_customer(
            save_fixture, workspace=workspace, email="x@example.com"
        )
        # Insert in NON-policy order so the ORDER BY is exercised.
        await save_fixture(
            Member(
                customer_id=customer.id,
                workspace_id=workspace.id,
                email="alice@example.com",
                role=MemberRole.member,
            )
        )
        owner = Member(
            customer_id=customer.id,
            workspace_id=workspace.id,
            email="ALICE@example.com",
            role=MemberRole.owner,
        )
        await save_fixture(owner)

        repo = MemberRepository.from_session(session)
        ordered = await repo.list_duplicates_for_dedupe(
            customer.id, "alice@example.com"
        )

        assert len(ordered) == 2
        assert ordered[0].id == owner.id
        assert ordered[0].role == MemberRole.owner

    async def test_billing_manager_beats_member(
        self,
        session: AsyncSession,
        save_fixture: SaveFixture,
        workspace: Workspace,
    ) -> None:
        # Pin: billing_manager > member by enum, even though
        # billing_manager < member alphabetically. The CASE
        # expression's the difference.
        customer = await create_customer(
            save_fixture, workspace=workspace, email="y@example.com"
        )
        await save_fixture(
            Member(
                customer_id=customer.id,
                workspace_id=workspace.id,
                email="bob@example.com",
                role=MemberRole.member,
            )
        )
        billing = Member(
            customer_id=customer.id,
            workspace_id=workspace.id,
            email="BOB@example.com",
            role=MemberRole.billing_manager,
        )
        await save_fixture(billing)

        repo = MemberRepository.from_session(session)
        ordered = await repo.list_duplicates_for_dedupe(customer.id, "bob@example.com")

        assert ordered[0].id == billing.id

    async def test_role_tie_broken_by_earliest_created_at(
        self,
        session: AsyncSession,
        save_fixture: SaveFixture,
        workspace: Workspace,
    ) -> None:
        # Same role → earliest registration wins. Pins the
        # "original first" semantic.
        from datetime import timedelta

        customer = await create_customer(
            save_fixture, workspace=workspace, email="z@example.com"
        )
        older = Member(
            customer_id=customer.id,
            workspace_id=workspace.id,
            email="carol@example.com",
            role=MemberRole.owner,
            created_at=now_utc() - timedelta(days=10),
        )
        newer = Member(
            customer_id=customer.id,
            workspace_id=workspace.id,
            email="CAROL@example.com",
            role=MemberRole.owner,
            created_at=now_utc(),
        )
        await save_fixture(older)
        await save_fixture(newer)

        repo = MemberRepository.from_session(session)
        ordered = await repo.list_duplicates_for_dedupe(
            customer.id, "carol@example.com"
        )

        assert ordered[0].id == older.id
        assert ordered[1].id == newer.id
