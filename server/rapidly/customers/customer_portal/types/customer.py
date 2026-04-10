"""Pydantic schemas for customer-portal customer profile and billing."""

from typing import Annotated

from rapidly.core.address import Address, AddressInput
from rapidly.core.types import (
    AuditableSchema,
    EmptyStrToNoneValidator,
    IdentifiableSchema,
    Schema,
)
from rapidly.models.customer import CustomerType


class CustomerPortalOAuthAccount(Schema):
    account_id: str
    account_username: str | None


class CustomerPortalCustomer(IdentifiableSchema, AuditableSchema):
    email: str
    email_verified: bool
    name: str | None
    billing_name: str | None
    billing_address: Address | None
    oauth_accounts: dict[str, CustomerPortalOAuthAccount]
    type: CustomerType | None = None


class CustomerPortalCustomerUpdate(Schema):
    billing_name: Annotated[str | None, EmptyStrToNoneValidator] = None
    billing_address: AddressInput | None = None
