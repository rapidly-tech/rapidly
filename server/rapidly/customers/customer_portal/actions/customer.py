"""Customer-portal customer service: profile access and Stripe billing portal.

Provides portal-scoped helpers for loading the authenticated customer's
profile, generating Stripe billing-portal sessions, and resolving
share entitlements.
"""

from typing import TYPE_CHECKING

from rapidly.customers.customer.queries import CustomerRepository
from rapidly.integrations.stripe import actions as stripe_service
from rapidly.models import Customer as CustomerModel
from rapidly.postgres import AsyncSession

from ..types.customer import (
    CustomerPortalCustomerUpdate,
)

if TYPE_CHECKING:
    from stripe.params._modify_customer_params import ModifyCustomerParams


class CustomerService:
    async def update(
        self,
        session: AsyncSession,
        customer: CustomerModel,
        customer_update: CustomerPortalCustomerUpdate,
    ) -> CustomerModel:
        if customer_update.billing_name is not None:
            customer.billing_name = customer_update.billing_name

        customer.billing_address = (
            customer_update.billing_address or customer.billing_address
        )

        repository = CustomerRepository.from_session(session)
        customer = await repository.update(
            customer,
            update_dict=customer_update.model_dump(
                exclude_unset=True,
                exclude={"billing_name", "billing_address"},
            ),
        )

        if customer.stripe_customer_id is not None:
            params: ModifyCustomerParams = {"email": customer.email}
            if customer.billing_name is not None and customer.name is None:
                params["name"] = customer.billing_name
            if customer.billing_address is not None:
                params["address"] = customer.billing_address.to_dict()
            await stripe_service.update_customer(
                customer.stripe_customer_id,
                **params,
            )

        return customer


customer = CustomerService()
