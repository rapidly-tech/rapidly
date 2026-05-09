"""Tests for ``rapidly/core/email.py``.

``EmailStrDNS`` is the deliverability-checking email type used on
every signup + email-change + customer-create body. The module's
documented contract has two parts:

1. **Syntax + deliverability** — wraps ``EmailStr`` with an
   ``AfterValidator`` that also checks the domain has live MX
   records
2. **Test-environment bypass** — during the test suite the
   ``email_validator.TEST_ENVIRONMENT`` flag short-circuits the
   DNS lookup so tests don't depend on network

Pinning both keeps the production deliverability guarantee AND the
test-ergonomics bypass visible.
"""

from __future__ import annotations

from typing import Annotated, get_args

import email_validator
import pytest
from pydantic import AfterValidator, BaseModel, EmailStr, TypeAdapter, ValidationError

from rapidly.core import email as E
from rapidly.core.email import (
    EmailNotValidError,
    EmailStrDNS,
    _assert_deliverable,
    validate_email,
)


class TestTestEnvironmentIsEnabled:
    def test_module_enabled_test_environment(self) -> None:
        # Pinning this prevents a regression where real DNS lookups
        # would slip into the test suite and make tests flaky on CI
        # (or worse, fail offline).
        assert email_validator.TEST_ENVIRONMENT is True


class TestValidateEmailHelper:
    def test_uses_check_deliverability(self) -> None:
        # ``validate_email`` is ``functools.partial(_upstream,
        # check_deliverability=True, ...)`` — if a regression
        # switched the default to False, the prod path would accept
        # syntactically-valid but undeliverable addresses.
        import functools

        assert isinstance(validate_email, functools.partial)
        assert validate_email.keywords.get("check_deliverability") is True


class TestAssertDeliverableHelper:
    def test_returns_address_unchanged_on_valid(self) -> None:
        # The validator must return the input (AfterValidator
        # contract) so downstream Pydantic sees the address.
        assert _assert_deliverable("alice@test.com") == "alice@test.com"

    def test_wraps_invalid_into_pydantic_custom_error(self) -> None:
        # Under TEST_ENVIRONMENT the upstream validator still
        # rejects obviously-malformed syntax. The helper must wrap
        # ``EmailNotValidError`` into a ``PydanticCustomError`` so
        # FastAPI renders a 422 with a field-level error, not a 500.
        from pydantic_core import PydanticCustomError

        with pytest.raises(PydanticCustomError):
            _assert_deliverable("not-an-email")


class TestEmailStrDNSAnnotation:
    def test_is_annotated_emailstr_with_aftervalidator(self) -> None:
        # Shape pin: ``Annotated[EmailStr, AfterValidator(...)]``.
        # A regression that replaced the wrapping with a plain
        # ``EmailStr`` would drop the deliverability layer silently.
        args = get_args(EmailStrDNS)
        # First arg is the base type; remainder carry metadata.
        assert args[0] is EmailStr
        # Some AfterValidator must be present.
        assert any(isinstance(m, AfterValidator) for m in args[1:])


class TestEmailStrDNSInPydanticModel:
    def test_accepts_valid_email(self) -> None:
        class _M(BaseModel):
            email: EmailStrDNS

        m = _M(email="alice@test.com")
        assert m.email == "alice@test.com"

    def test_rejects_malformed_syntax(self) -> None:
        class _M(BaseModel):
            email: EmailStrDNS

        with pytest.raises(ValidationError):
            _M(email="not-an-email")

    def test_rejects_missing_at_sign(self) -> None:
        class _M(BaseModel):
            email: EmailStrDNS

        with pytest.raises(ValidationError):
            _M(email="aliceatexample.com")


class TestExportedSymbols:
    def test_all_exports_are_present(self) -> None:
        # The ``__all__`` list is the documented public surface.
        # Removing an export would be a behaviour change visible to
        # the rest of the codebase.
        for name in ("EmailNotValidError", "EmailStrDNS", "validate_email"):
            assert name in E.__all__
            assert hasattr(E, name)

    def test_email_not_valid_error_is_upstream_class(self) -> None:
        # Re-exporting the upstream exception type lets callers
        # catch it without importing ``email_validator`` directly.
        assert EmailNotValidError is email_validator.EmailNotValidError


class TestTypeAdapterRoundtrip:
    def test_validates_via_typeadapter(self) -> None:
        # Direct TypeAdapter path — API code uses this to validate
        # lone email fields outside a model.
        adapter: TypeAdapter[Annotated[str, EmailStrDNS]] = TypeAdapter(EmailStrDNS)
        assert adapter.validate_python("alice@test.com") == "alice@test.com"

    def test_typeadapter_rejects_invalid(self) -> None:
        adapter: TypeAdapter[Annotated[str, EmailStrDNS]] = TypeAdapter(EmailStrDNS)
        with pytest.raises(ValidationError):
            adapter.validate_python("nope")
