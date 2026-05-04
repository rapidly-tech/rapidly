"""Pydantic schemas for login code requests and responses."""

from pydantic import field_validator

from rapidly.core.email import EmailStrDNS
from rapidly.core.http import get_safe_return_url
from rapidly.core.types import Schema
from rapidly.platform.user.types import UserSignupAttribution


class LoginCodeRequest(Schema):
    email: EmailStrDNS
    return_to: str | None = None
    attribution: UserSignupAttribution | None = None

    @field_validator("return_to")
    @classmethod
    def validate_return_to(cls, v: str | None) -> str:
        return get_safe_return_url(v)
