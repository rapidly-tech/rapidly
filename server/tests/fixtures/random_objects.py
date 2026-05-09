"""Factory functions for creating randomized test objects across all domains."""

import random
import string
import typing
import uuid
from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any, Literal

import pytest_asyncio
from typing_extensions import TypeIs

from rapidly.core.address import Address
from rapidly.core.utils import now_utc
from rapidly.enums import (
    AccountType,
    PaymentProcessor,
)
from rapidly.messaging.notification_recipient.types import NotificationRecipientPlatform
from rapidly.models import (
    Account,
    Customer,
    CustomField,
    Event,
    EventType,
    Member,
    Payment,
    Share,
    ShareCustomField,
    SharePriceCustom,
    SharePriceFixed,
    SharePriceFree,
    SharePriceSeatUnit,
    ShareVisibility,
    User,
    WebhookEndpoint,
    Workspace,
    WorkspaceMembership,
)
from rapidly.models.custom_field import (
    CustomFieldCheckbox,
    CustomFieldCheckboxProperties,
    CustomFieldNumber,
    CustomFieldNumberProperties,
    CustomFieldProperties,
    CustomFieldSelect,
    CustomFieldSelectProperties,
    CustomFieldText,
    CustomFieldTextProperties,
    CustomFieldType,
)
from rapidly.models.event import EventSource
from rapidly.models.member import MemberRole
from rapidly.models.notification_recipient import NotificationRecipient
from rapidly.models.payment import PaymentStatus
from rapidly.models.share_price import SharePriceAmountType
from rapidly.models.user import OAuthAccount, OAuthPlatform
from rapidly.models.webhook_endpoint import WebhookEventType, WebhookFormat
from tests.fixtures.database import SaveFixture

# ── String helpers ──


def rstr(prefix: str) -> str:
    return prefix + "".join(random.choices(string.ascii_uppercase + string.digits, k=6))


def lstr(suffix: str) -> str:
    return "".join(random.choices(string.ascii_uppercase + string.digits, k=6)) + suffix


# ── Workspace factories ──


async def create_workspace(
    save_fixture: SaveFixture, name_prefix: str = "testorg", **kwargs: Any
) -> Workspace:
    name = rstr(name_prefix)
    # Create workspaces in the past so they are grandfathered for payment readiness
    # unless created_at is explicitly provided
    if "created_at" not in kwargs:
        kwargs["created_at"] = datetime(2025, 7, 1, tzinfo=UTC)

    workspace = Workspace(
        name=name,
        slug=name,
        customer_invoice_prefix=name.upper(),
        avatar_url="https://avatars.githubusercontent.com/u/105373340?s=200&v=4",
        **kwargs,
    )
    await save_fixture(workspace)
    return workspace


@pytest_asyncio.fixture
async def workspace(save_fixture: SaveFixture) -> Workspace:
    return await create_workspace(save_fixture)


@pytest_asyncio.fixture
async def workspace_second(save_fixture: SaveFixture) -> Workspace:
    return await create_workspace(save_fixture)


@pytest_asyncio.fixture
async def second_workspace(save_fixture: SaveFixture) -> Workspace:
    return await create_workspace(save_fixture)


# ── User factories ──


async def create_oauth_account(
    save_fixture: SaveFixture,
    user: User,
    platform: OAuthPlatform,
) -> OAuthAccount:
    oauth_account = OAuthAccount(
        platform=platform,
        access_token="xxyyzz",
        account_id="xxyyzz",
        account_email="foo@bar.com",
        account_username=rstr("gh_username"),
        user_id=user.id,
    )
    await save_fixture(oauth_account)
    return oauth_account


async def create_user(
    save_fixture: SaveFixture,
    stripe_customer_id: str | None = None,
    email_verified: bool = True,
) -> User:
    user = User(
        id=uuid.uuid4(),
        email=rstr("test") + "@example.com",
        email_verified=email_verified,
        avatar_url="https://avatars.githubusercontent.com/u/47952?v=4",
        oauth_accounts=[],
        stripe_customer_id=stripe_customer_id,
    )
    await save_fixture(user)
    return user


@pytest_asyncio.fixture
async def user(save_fixture: SaveFixture) -> User:
    return await create_user(save_fixture)


@pytest_asyncio.fixture
async def user_second(save_fixture: SaveFixture) -> User:
    return await create_user(save_fixture)


@pytest_asyncio.fixture
async def workspace_membership(
    save_fixture: SaveFixture,
    workspace: Workspace,
    user: User,
) -> WorkspaceMembership:
    workspace_membership = WorkspaceMembership(user=user, workspace=workspace)
    await save_fixture(workspace_membership)
    return workspace_membership


@pytest_asyncio.fixture
async def workspace_membership_second(
    save_fixture: SaveFixture,
    workspace: Workspace,
    user_second: User,
) -> WorkspaceMembership:
    workspace_membership = WorkspaceMembership(user=user_second, workspace=workspace)
    await save_fixture(workspace_membership)
    return workspace_membership


# ── Custom field factories ──


@typing.overload
async def create_custom_field(
    save_fixture: SaveFixture,
    *,
    type: typing.Literal[CustomFieldType.text],
    slug: str,
    workspace: Workspace,
    name: str = "Custom Field",
    properties: CustomFieldTextProperties | None = None,
) -> CustomFieldText: ...
@typing.overload
async def create_custom_field(
    save_fixture: SaveFixture,
    *,
    type: typing.Literal[CustomFieldType.number],
    slug: str,
    workspace: Workspace,
    name: str = "Custom Field",
    properties: CustomFieldNumberProperties | None = None,
) -> CustomFieldNumber: ...
@typing.overload
async def create_custom_field(
    save_fixture: SaveFixture,
    *,
    type: typing.Literal[CustomFieldType.checkbox],
    slug: str,
    workspace: Workspace,
    name: str = "Custom Field",
    properties: CustomFieldCheckboxProperties | None = None,
) -> CustomFieldCheckbox: ...
@typing.overload
async def create_custom_field(
    save_fixture: SaveFixture,
    *,
    type: typing.Literal[CustomFieldType.select],
    slug: str,
    workspace: Workspace,
    name: str = "Custom Field",
    properties: CustomFieldSelectProperties | None = None,
) -> CustomFieldSelect: ...
async def create_custom_field(
    save_fixture: SaveFixture,
    *,
    type: CustomFieldType,
    slug: str,
    workspace: Workspace,
    name: str = "Custom Field",
    properties: CustomFieldProperties | None = None,
) -> CustomField:
    model = type.get_model()
    custom_field = model(
        type=type,
        slug=slug,
        name=name,
        properties=properties or {},
        workspace=workspace,
    )
    await save_fixture(custom_field)
    return custom_field


# ── Share & pricing factories ──


type PriceFixtureType = (
    tuple[int, str]
    | tuple[int, int | None, int | None, str]
    | tuple[None, str]
    | tuple[Literal["seat"], int, str]
)


def _is_seat_price_fixture_type(
    price: PriceFixtureType,
) -> TypeIs[tuple[Literal["seat"], int, str]]:
    return len(price) == 3 and price[0] == "seat"


async def create_product(
    save_fixture: SaveFixture,
    *,
    workspace: Workspace,
    recurring_interval_count: int | None = 1,
    name: str = "Share",
    is_archived: bool = False,
    visibility: ShareVisibility = ShareVisibility.public,
    prices: Sequence[PriceFixtureType] = [(1000, "usd")],
    attached_custom_fields: Sequence[tuple[CustomField, bool]] = [],
) -> Share:
    share = Share(
        name=name,
        description="Description",
        is_archived=is_archived,
        visibility=visibility,
        workspace=workspace,
        all_prices=[],
        prices=[],
        share_medias=[],
        attached_custom_fields=[
            ShareCustomField(custom_field=custom_field, required=required, order=i)
            for i, (custom_field, required) in enumerate(attached_custom_fields)
        ],
    )
    await save_fixture(share)

    for price in prices:
        product_price: (
            SharePriceFixed | SharePriceCustom | SharePriceFree | SharePriceSeatUnit
        )
        if len(price) == 2:
            amount, currency = price
            if amount is None:
                product_price = await create_product_price_free(
                    save_fixture, share=share
                )
            else:
                product_price = await create_product_price_fixed(
                    save_fixture, share=share, amount=amount, currency=currency
                )
        elif _is_seat_price_fixture_type(price):
            _, price_per_seat, currency = price
            product_price = await create_product_price_seat_unit(
                save_fixture,
                share=share,
                price_per_seat=price_per_seat,
                currency=currency,
            )
        else:
            (
                minimum_amount,
                maximum_amount,
                preset_amount,
                currency,
            ) = price
            product_price = await create_product_price_custom(
                save_fixture,
                share=share,
                minimum_amount=minimum_amount,
                maximum_amount=maximum_amount,
                preset_amount=preset_amount,
                currency=currency,
            )

        share.prices.append(product_price)
        share.all_prices.append(product_price)

    return share


async def create_product_price_fixed(
    save_fixture: SaveFixture,
    *,
    share: Share,
    amount: int = 1000,
    currency: str = "usd",
    is_archived: bool = False,
) -> SharePriceFixed:
    price = SharePriceFixed(
        price_amount=amount,
        price_currency=currency,
        share=share,
        is_archived=is_archived,
    )
    await save_fixture(price)
    return price


async def create_product_price_custom(
    save_fixture: SaveFixture,
    *,
    share: Share,
    minimum_amount: int = 50,
    maximum_amount: int | None = None,
    preset_amount: int | None = None,
    currency: str = "usd",
) -> SharePriceCustom:
    price = SharePriceCustom(
        price_currency=currency,
        minimum_amount=minimum_amount,
        maximum_amount=maximum_amount,
        preset_amount=preset_amount,
        share=share,
    )
    await save_fixture(price)
    return price


async def create_product_price_free(
    save_fixture: SaveFixture,
    *,
    share: Share,
    currency: str = "usd",
) -> SharePriceFree:
    price = SharePriceFree(
        share=share,
        price_currency=currency,
    )
    await save_fixture(price)
    return price


async def create_product_price_seat_unit(
    save_fixture: SaveFixture,
    *,
    share: Share | None = None,
    price_per_seat: int = 1000,
    minimum_seats: int = 1,
    maximum_seats: int | None = None,
    currency: str = "usd",
) -> SharePriceSeatUnit:
    """Create a seat-based price with a single tier.

    Args:
        price_per_seat: Price per seat in cents.
        minimum_seats: Minimum seats allowed (first tier's min_seats).
        maximum_seats: Maximum seats allowed (last tier's max_seats). None for unlimited.
    """
    seat_tiers: dict[str, typing.Any] = {
        "tiers": [
            {
                "min_seats": minimum_seats,
                "max_seats": maximum_seats,
                "price_per_seat": price_per_seat,
            }
        ]
    }

    price = SharePriceSeatUnit(
        price_currency=currency,
        seat_tiers=seat_tiers,
        share=share,
    )
    assert price.amount_type == SharePriceAmountType.seat_based
    await save_fixture(price)
    return price


# ── Customer factories ──


async def create_customer(
    save_fixture: SaveFixture,
    *,
    workspace: Workspace,
    external_id: str | None = None,
    email: str = "customer@example.com",
    email_verified: bool = False,
    name: str = "Customer",
    stripe_customer_id: str | None = "STRIPE_CUSTOMER_ID",
    billing_address: Address | None = None,
    user_metadata: dict[str, Any] = {},
) -> Customer:
    customer = Customer(
        external_id=external_id,
        email=email,
        email_verified=email_verified,
        name=name,
        stripe_customer_id=stripe_customer_id,
        workspace=workspace,
        billing_address=billing_address,
        user_metadata=user_metadata,
    )
    await save_fixture(customer)
    return customer


@pytest_asyncio.fixture
async def share(save_fixture: SaveFixture, workspace: Workspace) -> Share:
    return await create_product(
        save_fixture,
        workspace=workspace,
    )


@pytest_asyncio.fixture
async def product_one_time(save_fixture: SaveFixture, workspace: Workspace) -> Share:
    return await create_product(
        save_fixture,
        workspace=workspace,
    )


@pytest_asyncio.fixture
async def product_one_time_custom_price(
    save_fixture: SaveFixture, workspace: Workspace
) -> Share:
    return await create_product(
        save_fixture,
        workspace=workspace,
        prices=[(50, None, None, "usd")],
    )


@pytest_asyncio.fixture
async def product_one_time_free_price(
    save_fixture: SaveFixture, workspace: Workspace
) -> Share:
    return await create_product(
        save_fixture,
        workspace=workspace,
        prices=[(None, "usd")],
    )


@pytest_asyncio.fixture
async def product_one_time_multiple_currencies(
    save_fixture: SaveFixture, workspace: Workspace
) -> Share:
    return await create_product(
        save_fixture,
        workspace=workspace,
        prices=[(1000, "usd"), (900, "eur"), (800, "gbp")],
    )


@pytest_asyncio.fixture
async def product_recurring_custom_price(
    save_fixture: SaveFixture, workspace: Workspace
) -> Share:
    return await create_product(
        save_fixture,
        workspace=workspace,
        prices=[(50, None, None, "usd")],
    )


@pytest_asyncio.fixture
async def product_recurring_free_price(
    save_fixture: SaveFixture, workspace: Workspace
) -> Share:
    return await create_product(
        save_fixture,
        workspace=workspace,
        prices=[(None, "usd")],
    )


@pytest_asyncio.fixture
async def product_recurring_every_second_month(
    save_fixture: SaveFixture, workspace: Workspace
) -> Share:
    return await create_product(
        save_fixture,
        workspace=workspace,
    )


@pytest_asyncio.fixture
async def product_recurring_multiple_currencies(
    save_fixture: SaveFixture, workspace: Workspace
) -> Share:
    return await create_product(
        save_fixture,
        workspace=workspace,
        prices=[(1000, "usd"), (900, "eur"), (800, "gbp")],
    )


@pytest_asyncio.fixture
async def product_second(save_fixture: SaveFixture, workspace: Workspace) -> Share:
    return await create_product(
        save_fixture,
        workspace=workspace,
        prices=[(2000, "usd")],
    )


@pytest_asyncio.fixture
async def product_workspace_second(
    save_fixture: SaveFixture, workspace_second: Workspace
) -> Share:
    return await create_product(
        save_fixture,
        workspace=workspace_second,
    )


@pytest_asyncio.fixture
async def products(
    share: Share,
    product_second: Share,
    product_workspace_second: Share,
) -> list[Share]:
    return [share, product_second, product_workspace_second]


@pytest_asyncio.fixture
async def workspace_account(
    save_fixture: SaveFixture, workspace: Workspace, user: User
) -> Account:
    account = Account(
        account_type=AccountType.stripe,
        admin_id=user.id,
        country="US",
        currency="USD",
        is_details_submitted=True,
        is_charges_enabled=True,
        is_payouts_enabled=True,
        stripe_id="STRIPE_ACCOUNT_ID",
    )
    await save_fixture(account)
    workspace.account = account
    await save_fixture(workspace)
    return account


@pytest_asyncio.fixture
async def workspace_second_members(
    save_fixture: SaveFixture, workspace_second: Workspace
) -> list[User]:
    users: list[User] = []
    for _ in range(5):
        user = await create_user(save_fixture)
        workspace_membership = WorkspaceMembership(
            user=user, workspace=workspace_second
        )
        await save_fixture(workspace_membership)
        users.append(user)
    return users


@pytest_asyncio.fixture
async def customer(
    save_fixture: SaveFixture,
    workspace: Workspace,
) -> Customer:
    return await create_customer(
        save_fixture,
        workspace=workspace,
        email=lstr("customer@example.com"),
        stripe_customer_id=lstr("STRIPE_CUSTOMER_ID"),
    )


@pytest_asyncio.fixture
async def member_second(
    save_fixture: SaveFixture,
    customer: Customer,
    workspace: Workspace,
) -> Member:
    return await create_member(
        save_fixture,
        customer=customer,
        workspace=workspace,
        email=lstr("member.second@example.com"),
        role=MemberRole.member,
    )


@pytest_asyncio.fixture
async def customer_second(
    save_fixture: SaveFixture,
    workspace: Workspace,
) -> Customer:
    return await create_customer(
        save_fixture,
        workspace=workspace,
        email=lstr("customer.second@example.com"),
        stripe_customer_id=lstr("STRIPE_CUSTOMER_ID_2"),
    )


@pytest_asyncio.fixture
async def customer_external_id(
    save_fixture: SaveFixture,
    workspace: Workspace,
) -> Customer:
    return await create_customer(
        save_fixture,
        workspace=workspace,
        external_id=lstr("CUSTOMER_EXTERNAL_ID"),
        email=lstr("customer.external_id@example.com"),
        stripe_customer_id=lstr("STRIPE_CUSTOMER_ID_3"),
    )


@pytest_asyncio.fixture
async def customer_workspace_second(
    save_fixture: SaveFixture,
    workspace_second: Workspace,
) -> Customer:
    return await create_customer(
        save_fixture,
        workspace=workspace_second,
        email=lstr("customer.workspace_second@example.com"),
        stripe_customer_id=lstr("STRIPE_CUSTOMER_ID_4"),
    )


# ── Member factories ──


async def create_member(
    save_fixture: SaveFixture,
    *,
    customer: Customer,
    workspace: Workspace,
    role: MemberRole = MemberRole.member,
    email: str | None = None,
    name: str = "Test Member",
) -> Member:
    """Create a member for testing purposes."""
    member = Member(
        customer_id=customer.id,
        workspace_id=workspace.id,
        email=email or customer.email,
        name=name,
        role=role,
    )
    await save_fixture(member)
    # Attach the customer relationship for easy access
    member.customer = customer
    return member


@pytest_asyncio.fixture
async def member_owner(
    save_fixture: SaveFixture,
    customer: Customer,
    workspace: Workspace,
) -> Member:
    """Member with owner role."""
    return await create_member(
        save_fixture,
        customer=customer,
        workspace=workspace,
        role=MemberRole.owner,
        name="Owner Member",
    )


@pytest_asyncio.fixture
async def member_billing_manager(
    save_fixture: SaveFixture,
    customer: Customer,
    workspace: Workspace,
) -> Member:
    """Member with billing_manager role."""
    return await create_member(
        save_fixture,
        customer=customer,
        workspace=workspace,
        role=MemberRole.billing_manager,
        name="Billing Manager Member",
    )


@pytest_asyncio.fixture
async def member(
    save_fixture: SaveFixture,
    customer: Customer,
    workspace: Workspace,
) -> Member:
    """Member with regular member role (read-only)."""
    return await create_member(
        save_fixture,
        customer=customer,
        workspace=workspace,
        role=MemberRole.member,
        name="Regular Member",
    )


# ── Event factories ──


METER_TEST_EVENT = "TEST_EVENT"


async def create_event(
    save_fixture: SaveFixture,
    *,
    workspace: Workspace,
    source: EventSource = EventSource.user,
    name: str = METER_TEST_EVENT,
    timestamp: datetime | None = None,
    customer: Customer | None = None,
    external_customer_id: str | None = None,
    external_id: str | None = None,
    parent_id: uuid.UUID | None = None,
    metadata: dict[str, str | int | bool | float | Any] | None = None,
    event_type: EventType | None = None,
) -> Event:
    event = Event(
        timestamp=timestamp or now_utc(),
        source=source,
        name=name,
        customer_id=customer.id if customer else None,
        external_customer_id=external_customer_id,
        external_id=external_id,
        parent_id=parent_id,
        workspace=workspace,
        user_metadata=metadata or {},
        event_type_id=event_type.id if event_type else None,
    )
    await save_fixture(event)
    return event


# ── Notification factories ──


async def create_notification_recipient(
    save_fixture: SaveFixture,
    *,
    user: User,
    expo_push_token: str,
    platform: NotificationRecipientPlatform = NotificationRecipientPlatform.ios,
) -> NotificationRecipient:
    notification_recipient = NotificationRecipient(
        platform=platform,
        expo_push_token=expo_push_token,
        user_id=user.id,
    )
    await save_fixture(notification_recipient)
    return notification_recipient


# ── Account factories ──


async def create_account(
    save_fixture: SaveFixture,
    workspace: Workspace,
    user: User,
    *,
    status: Account.Status = Account.Status.ACTIVE,
    country: str = "US",
    currency: str = "usd",
    account_type: AccountType = AccountType.stripe,
    stripe_id: str | None = "STRIPE_ID",
    processor_fees_applicable: bool = True,
    fee_basis_points: int | None = None,
    fee_fixed: int | None = None,
    is_payouts_enabled: bool = True,
    billing_name: str | None = None,
    billing_address: Address | None = None,
) -> Account:
    account = Account(
        status=status,
        account_type=account_type,
        admin_id=user.id,
        country=country,
        currency=currency,
        is_details_submitted=True,
        is_charges_enabled=True,
        is_payouts_enabled=is_payouts_enabled,
        processor_fees_applicable=processor_fees_applicable,
        stripe_id=stripe_id,
        _platform_fee_percent=fee_basis_points,
        _platform_fee_fixed=fee_fixed,
        billing_name=billing_name,
        billing_address=billing_address,
    )
    await save_fixture(account)
    workspace.account = account
    await save_fixture(workspace)
    return account


@pytest_asyncio.fixture
async def account(
    save_fixture: SaveFixture, workspace: Workspace, user: User
) -> Account:
    return await create_account(save_fixture, workspace, user)


# ── Payment factories ──


async def create_payment(
    save_fixture: SaveFixture,
    workspace: Workspace,
    *,
    processor: PaymentProcessor = PaymentProcessor.stripe,
    status: PaymentStatus = PaymentStatus.succeeded,
    amount: int = 1000,
    currency: str = "usd",
    method: str = "card",
    method_metadata: dict[str, Any] = {},
    customer_email: str | None = "customer@example.com",
    processor_id: str | None = None,
    decline_reason: str | None = None,
    decline_message: str | None = None,
    risk_level: str | None = None,
    risk_score: int | None = None,
) -> Payment:
    payment = Payment(
        processor=processor,
        status=status,
        amount=amount,
        currency=currency,
        method=method,
        method_metadata=method_metadata,
        customer_email=customer_email,
        processor_id=processor_id or rstr("PAYMENT_PROCESSOR_ID"),
        decline_reason=decline_reason,
        decline_message=decline_message,
        risk_level=risk_level,
        risk_score=risk_score,
        workspace=workspace,
    )
    await save_fixture(payment)
    return payment


@pytest_asyncio.fixture
async def payment(save_fixture: SaveFixture, workspace: Workspace) -> Payment:
    return await create_payment(save_fixture, workspace)


# ── Event type factories ──


async def create_event_type(
    save_fixture: SaveFixture,
    *,
    workspace: Workspace,
    name: str = "test.event",
    label: str = "Test Event",
) -> EventType:
    event_type = EventType(
        name=name,
        label=label,
        workspace_id=workspace.id,
    )
    await save_fixture(event_type)
    return event_type


@pytest_asyncio.fixture
async def event_type(
    save_fixture: SaveFixture,
    workspace: Workspace,
) -> EventType:
    return await create_event_type(save_fixture, workspace=workspace)


# ── Webhook factories ──


async def create_webhook_endpoint(
    save_fixture: SaveFixture,
    *,
    workspace: Workspace,
    events: list[WebhookEventType] | None = None,
) -> WebhookEndpoint:
    webhook_endpoint = WebhookEndpoint(
        url="https://example.com/webhook",
        format=WebhookFormat.raw,
        secret="SECRET",
        events=events or list(WebhookEventType),
        workspace=workspace,
    )
    await save_fixture(webhook_endpoint)
    return webhook_endpoint
