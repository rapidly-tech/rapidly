"""Pydantic schemas for work-item vote endpoints."""

from typing import Annotated, Literal

from fastapi import Path
from pydantic import UUID4, Field

from rapidly.core.types import AuditableSchema, IdentifiableSchema, Schema

WorkItemVoteID = Annotated[UUID4, Path(description="The vote ID.")]

# Restrict to ``-1`` (downvote) or ``+1`` (upvote).  ``0`` is reserved
# for a possible "retracted" future state; today, retracting means
# DELETE on the row.
VoteValue = Literal[-1, 1]


class WorkItemVote(IdentifiableSchema, AuditableSchema):
    work_item_id: UUID4
    user_id: UUID4
    vote: int


class WorkItemVoteCast(Schema):
    work_item_id: UUID4 = Field(..., description="The work item to vote on.")
    vote: VoteValue = Field(..., description="-1 to downvote, +1 to upvote.")
