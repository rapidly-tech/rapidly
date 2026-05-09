"""Email address validation with DNS deliverability checking.

Exports ``EmailStrDNS``, a Pydantic-compatible annotated type that
validates both address syntax *and* whether the domain has live MX
records.  Also re-exports ``validate_email`` for use in non-Pydantic
contexts.
"""

from __future__ import annotations

import functools
from typing import Annotated

import email_validator
from email_validator import EmailNotValidError, caching_resolver
from email_validator import validate_email as _upstream_validate
from pydantic import AfterValidator, EmailStr
from pydantic_core import PydanticCustomError

from rapidly.config import settings

# Disable real DNS lookups during the test suite.
if settings.is_testing():
    email_validator.TEST_ENVIRONMENT = True

_resolver = caching_resolver()

validate_email = functools.partial(
    _upstream_validate,
    check_deliverability=True,
    dns_resolver=_resolver,
)


def _assert_deliverable(address: str) -> str:
    """Pydantic ``AfterValidator`` that rejects undeliverable domains."""
    try:
        validate_email(address)
    except EmailNotValidError as err:
        raise PydanticCustomError(
            "value_error",
            "{email} is not a valid email address: {reason}",
            {"email": address, "reason": str(err)},
        ) from err
    return address


EmailStrDNS = Annotated[EmailStr, AfterValidator(_assert_deliverable)]

__all__ = ["EmailNotValidError", "EmailStrDNS", "validate_email"]
