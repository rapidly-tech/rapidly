"""Tests for customer repository queries."""

import pytest
from pytest_mock import MockerFixture

from rapidly.customers.customer.queries import CustomerRepository
from rapidly.models import Customer, Workspace
from rapidly.models.webhook_endpoint import WebhookEventType
from rapidly.postgres import AsyncSession
from tests.fixtures.database import SaveFixture


@pytest.fixture
def repository(session: AsyncSession) -> CustomerRepository:
    return CustomerRepository.from_session(session)


@pytest.mark.asyncio
async def test_get_by_id(
    save_fixture: SaveFixture, customer: Customer, repository: CustomerRepository
) -> None:
    customer.set_deleted_at()
    await save_fixture(customer)

    result = await repository.get_by_id(customer.id, include_deleted=False)
    assert result is None

    result = await repository.get_by_id(customer.id, include_deleted=True)
    assert result == customer


@pytest.mark.asyncio
async def test_create_context(
    mocker: MockerFixture,
    session: AsyncSession,
    repository: CustomerRepository,
    workspace: Workspace,
) -> None:
    enqueue_job_mock = mocker.patch("rapidly.customers.customer.queries.dispatch_task")

    async with repository.create_context(
        Customer(email="customer@example.com", workspace=workspace)
    ) as customer:
        assert customer.id is not None
        await session.flush()

    enqueue_job_mock.assert_any_call(
        "customer.webhook", WebhookEventType.customer_created, customer.id
    )

    enqueue_job_mock.reset_mock()

    with pytest.raises(RuntimeError):
        async with repository.create_context(
            Customer(email="customer2@example.com", workspace=workspace)
        ) as customer:
            # Simulate an error during context execution
            raise RuntimeError("Simulated error")

    enqueue_job_mock.assert_not_called()


@pytest.mark.asyncio
async def test_find_case_insensitive_email_duplicates_returns_empty_on_clean_db(
    repository: CustomerRepository,
    workspace: Workspace,
) -> None:
    """Smoke: on a workspace with no active case-insensitive
    duplicates, the finder returns the empty list.

    Integration-tested rather than data-tested because the current
    ``Customer`` model still declares a GLOBAL unique on
    ``lower(email), deleted_at`` (``postgresql_nulls_not_distinct``)
    that would reject any fixture creating active duplicates. The
    smoke test is enough to prove the SQL is valid PostgreSQL and
    the empty-case return shape. The four load-bearing properties
    (active-only / case-insensitive / workspace-scoped / count>1)
    are visible in the 6-line query body in
    ``CustomerRepository.find_case_insensitive_email_duplicates``.
    """
    duplicates = await repository.find_case_insensitive_email_duplicates()
    assert duplicates == []
