"""Pydantic schemas for work-item subscriber endpoints."""

from typing import Annotated

from fastapi import Path
from pydantic import UUID4, Field

from rapidly.core.types import AuditableSchema, IdentifiableSchema, Schema

WorkItemSubscriberID = Annotated[
    UUID4, Path(description="The work-item subscriber ID.")
]


class WorkItemSubscriber(IdentifiableSchema, AuditableSchema):
    work_item_id: UUID4
    user_id: UUID4


class WorkItemSubscribeCreate(Schema):
    """Subscribe the caller to a work item.

    The ``user_id`` is intentionally *not* in the request body — the
    caller can only subscribe themselves.  Admin-driven subscription
    of someone else can be added later with a separate endpoint.
    """

    work_item_id: UUID4 = Field(..., description="The work item to subscribe to.")
