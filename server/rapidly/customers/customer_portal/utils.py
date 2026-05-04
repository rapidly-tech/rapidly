"""Customer-portal auth helpers: extract customer from union auth subjects."""

from uuid import UUID

from rapidly.identity.auth.models import AuthPrincipal, Customer, Member
from rapidly.models import Customer as CustomerModel


def get_customer(
    auth_subject: AuthPrincipal[Customer | Member],
) -> CustomerModel:
    """Extract the ``Customer`` model from an authenticated portal subject.

    For ``Customer`` principals the subject is returned directly.
    For ``Member`` principals the related customer is returned via
    ``member.customer``.
    """
    subject = auth_subject.subject
    if isinstance(subject, CustomerModel):
        return subject
    if isinstance(subject, Member):
        return subject.customer
    raise TypeError(f"Unexpected auth subject type: {type(subject)}")


def get_customer_id(
    auth_subject: AuthPrincipal[Customer | Member],
) -> UUID:
    """Return the customer ID from an authenticated portal subject."""
    return get_customer(auth_subject).id
