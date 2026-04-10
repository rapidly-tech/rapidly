"""Pydantic schemas for customer state responses."""

from .customer import CustomerBase


class CustomerState(CustomerBase):
    """A customer state snapshot (currently identical to the base schema)."""
