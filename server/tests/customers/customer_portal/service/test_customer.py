"""Tests for customer portal customer service logic."""

from unittest.mock import MagicMock

import pytest
from pytest_mock import MockerFixture

from rapidly.core.address import AddressInput, CountryAlpha2Input
from rapidly.customers.customer_portal.actions.customer import (
    customer as customer_service,
)
from rapidly.customers.customer_portal.types.customer import (
    CustomerPortalCustomerUpdate,
)
from rapidly.integrations.stripe import actions as stripe_actions
from rapidly.models import Workspace
from rapidly.postgres import AsyncSession
from tests.fixtures.database import SaveFixture
from tests.fixtures.random_objects import create_customer


@pytest.fixture(autouse=True)
def stripe_service_mock(mocker: MockerFixture) -> MagicMock:
    mock = MagicMock(spec=stripe_actions)
    mocker.patch(
        "rapidly.customers.customer_portal.actions.customer.stripe_service", new=mock
    )
    return mock


@pytest.mark.asyncio
class TestUpdate:
    async def test_billing_name_update(
        self,
        save_fixture: SaveFixture,
        session: AsyncSession,
        workspace: Workspace,
    ) -> None:
        customer = await create_customer(
            save_fixture,
            workspace=workspace,
        )

        updated_customer = await customer_service.update(
            session,
            customer,
            CustomerPortalCustomerUpdate(
                billing_name="Rapidly Software Inc.",
            ),
        )

        assert updated_customer.billing_name == "Rapidly Software Inc."

    async def test_valid(
        self,
        save_fixture: SaveFixture,
        session: AsyncSession,
        workspace: Workspace,
        stripe_service_mock: MagicMock,
    ) -> None:
        customer = await create_customer(save_fixture, workspace=workspace)

        updated_customer = await customer_service.update(
            session,
            customer,
            CustomerPortalCustomerUpdate(
                billing_name="Rapidly Software Inc.",
                billing_address=AddressInput(country=CountryAlpha2Input("FR")),
            ),
        )

        assert updated_customer.billing_name == "Rapidly Software Inc."
        assert updated_customer.billing_address is not None
        assert updated_customer.billing_address.country == "FR"

        stripe_service_mock.update_customer.assert_called_once()
