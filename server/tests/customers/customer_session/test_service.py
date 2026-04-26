"""Tests for customer session service logic."""

import pytest
from sqlalchemy import select

from rapidly.customers.customer_session.actions import (
    customer_session as customer_session_service,
)
from rapidly.identity.auth.models import AuthPrincipal
from rapidly.models import Member, User, Workspace, WorkspaceMembership
from rapidly.models.member import MemberRole
from rapidly.postgres import AsyncSession
from tests.fixtures.auth import AuthSubjectFixture
from tests.fixtures.database import SaveFixture
from tests.fixtures.random_objects import create_customer


@pytest.mark.asyncio
class TestCreateGracefulFallback:
    """Tests for graceful owner member auto-creation in customer session service."""

    @pytest.mark.auth(
        AuthSubjectFixture(subject="user"),
        AuthSubjectFixture(subject="workspace"),
    )
    async def test_auto_creates_owner_member_for_customer_session(
        self,
        session: AsyncSession,
        save_fixture: SaveFixture,
        workspace: Workspace,
        user: User,
        workspace_membership: WorkspaceMembership,
        auth_subject: AuthPrincipal[User | Workspace],
    ) -> None:
        """When member_model enabled but customer has no owner member,
        auto-create one and return MemberSession."""
        workspace.feature_settings = {"member_model_enabled": True}
        await save_fixture(workspace)

        customer = await create_customer(
            save_fixture,
            workspace=workspace,
            email="no-member@example.com",
        )

        from rapidly.customers.customer_session.types import (
            CustomerSessionCustomerIDCreate,
        )

        create_schema = CustomerSessionCustomerIDCreate(
            customer_id=customer.id,
        )

        result = await customer_session_service.create(
            session, auth_subject, create_schema
        )

        # Should succeed — an owner member was auto-created
        assert result is not None

        # Verify the owner member was created
        stmt = select(Member).where(
            Member.customer_id == customer.id,
            Member.role == MemberRole.owner,
            Member.deleted_at.is_(None),
        )
        db_result = await session.execute(stmt)
        members = db_result.scalars().all()
        assert len(members) == 1
        assert members[0].email == "no-member@example.com"

    @pytest.mark.auth(
        AuthSubjectFixture(subject="user"),
        AuthSubjectFixture(subject="workspace"),
    )
    async def test_returns_customer_session_when_flag_disabled(
        self,
        session: AsyncSession,
        save_fixture: SaveFixture,
        workspace: Workspace,
        user: User,
        workspace_membership: WorkspaceMembership,
        auth_subject: AuthPrincipal[User | Workspace],
    ) -> None:
        """When member_model disabled, should return CustomerSession (not MemberSession)."""
        # workspace defaults to member_model_enabled=false
        customer = await create_customer(
            save_fixture,
            workspace=workspace,
            email="legacy@example.com",
        )

        from rapidly.customers.customer_session.types import (
            CustomerSessionCustomerIDCreate,
        )
        from rapidly.models import CustomerSession

        create_schema = CustomerSessionCustomerIDCreate(
            customer_id=customer.id,
        )

        result = await customer_session_service.create(
            session, auth_subject, create_schema
        )

        assert result is not None
        assert isinstance(result, CustomerSession)
