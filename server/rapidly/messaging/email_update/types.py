"""Email-update request schema with DNS-validated email and safe return URL."""

from pydantic import field_validator

from rapidly.core.email import EmailStrDNS
from rapidly.core.http import get_safe_return_url
from rapidly.core.types import Schema


class EmailUpdateRequest(Schema):
    email: EmailStrDNS
    return_to: str | None = None

    @field_validator("return_to")
    @classmethod
    def validate_return_to(cls, v: str | None) -> str:
        return get_safe_return_url(v)
