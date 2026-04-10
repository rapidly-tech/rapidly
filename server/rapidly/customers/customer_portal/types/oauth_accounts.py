"""Pydantic schemas for customer portal OAuth account responses."""

from rapidly.core.types import Schema


class AuthorizeResponse(Schema):
    url: str
