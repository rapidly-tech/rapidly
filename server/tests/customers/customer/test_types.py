"""Tests for ``rapidly/customers/customer/types/customer.py``.

Complements the existing ``test_schemas.py`` (DB-backed external_id
roundtrip) with pins on the pure-Pydantic invariants:

- ``CustomerNameInput`` stacks ``MaxLen(256)`` + ``EmptyStrToNoneValidator``
- ``CustomerCreate`` / ``CustomerUpdate`` ``external_id`` runs through
  ``EmptyStrToNoneValidator`` — blank submissions coerce to None so
  the unique ``(workspace_id, external_id)`` index doesn't collide
  on whitespace
- ``CustomerBase.avatar_url`` computed field:
  - Personal email (``gmail.com`` etc.) → Gravatar with SHA-256 hash
  - Business domain (LOGO_DEV key set) → logo.dev URL
  - No LOGO_DEV key → Gravatar fallback (dev environment)
  - Email is lowercased before hashing — avatars stable across
    ``Alice@Example.com`` vs ``alice@example.com``
"""

from __future__ import annotations

import hashlib
from uuid import uuid4

import pytest
from pydantic import ValidationError

from rapidly.customers.customer.types.customer import (
    Customer,
    CustomerCreate,
    CustomerUpdate,
    CustomerWithMembers,
)

# ── Name input ──


class TestCustomerNameInput:
    def test_max_256_chars(self) -> None:
        with pytest.raises(ValidationError):
            CustomerCreate(email="c@test.com", name="a" * 257)

    def test_256_char_accepted(self) -> None:
        body = CustomerCreate(email="c@test.com", name="a" * 256)
        assert body.name == "a" * 256

    def test_whitespace_becomes_none(self) -> None:
        # ``EmptyStrToNoneValidator`` stacked on CustomerNameInput.
        body = CustomerCreate(email="c@test.com", name="   ")
        assert body.name is None


class TestExternalIdCoercion:
    def test_create_blank_external_id_coerces_to_none(self) -> None:
        # The "forgot to strip the field" case — a blank submission
        # must not collide with another customer's real external_id
        # on the unique ``(workspace_id, external_id)`` index.
        body = CustomerCreate(email="c@test.com", external_id="")
        assert body.external_id is None

    def test_create_whitespace_external_id_coerces_to_none(self) -> None:
        body = CustomerCreate(email="c@test.com", external_id="   ")
        assert body.external_id is None

    def test_create_valid_external_id_passes(self) -> None:
        body = CustomerCreate(email="c@test.com", external_id="usr_1337")
        assert body.external_id == "usr_1337"

    def test_update_blank_external_id_coerces_to_none(self) -> None:
        body = CustomerUpdate(external_id="")
        assert body.external_id is None


class TestCustomerCreateShape:
    def test_requires_email(self) -> None:
        with pytest.raises(ValidationError):
            CustomerCreate.model_validate({})

    def test_optional_fields_default_to_none(self) -> None:
        body = CustomerCreate(email="c@test.com")
        assert body.external_id is None
        assert body.name is None
        assert body.billing_address is None
        assert body.type is None
        assert body.workspace_id is None
        assert body.owner is None


class TestCustomerUpdateIsPartial:
    def test_all_fields_optional(self) -> None:
        body = CustomerUpdate()
        assert body.email is None
        assert body.name is None
        assert body.billing_address is None
        assert body.external_id is None
        assert body.type is None


# ── avatar_url computed field ──


def _build_customer(email: str) -> Customer:
    # Construct a minimal Customer via ``model_validate`` so the
    # required fields don't interfere with the avatar_url branch
    # under test.
    return Customer.model_validate(
        {
            "id": uuid4(),
            "created_at": "2026-01-01T00:00:00+00:00",
            "modified_at": "2026-01-01T00:00:00+00:00",
            "external_id": None,
            "email": email,
            "email_verified": False,
            "type": None,
            "name": None,
            "billing_address": None,
            "workspace_id": uuid4(),
            "deleted_at": None,
            "metadata": {},
        }
    )


def _avatar_url(email: str) -> str:
    # ``avatar_url`` is a ``@computed_field`` method; typing sees the
    # reference as ``Callable[[], str]``. Serialising through
    # ``model_dump`` gives the string the same way the API would
    # return it to callers.
    data = _build_customer(email).model_dump()
    return str(data["avatar_url"])


class TestAvatarUrlGravatarPath:
    def test_personal_email_uses_gravatar(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(
            "rapidly.customers.customer.types.customer.settings.LOGO_DEV_PUBLISHABLE_KEY",
            "k",
        )
        # gmail.com is in PERSONAL_EMAIL_DOMAINS — must hit the
        # Gravatar path even if LOGO_DEV is configured.
        url = _avatar_url("alice@gmail.com")
        assert "gravatar.com" in url
        expected_hash = hashlib.sha256(b"alice@gmail.com").hexdigest()
        assert expected_hash in url

    def test_missing_logo_dev_key_uses_gravatar(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Dev environments often don't have a LOGO_DEV key — the
        # fallback must still yield a valid Gravatar URL, never an
        # empty / invalid string.
        monkeypatch.setattr(
            "rapidly.customers.customer.types.customer.settings.LOGO_DEV_PUBLISHABLE_KEY",
            None,
        )
        url = _avatar_url("cto@acme.com")
        assert "gravatar.com" in url

    def test_email_is_lowercased_before_hashing(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Gravatar's hash input must be the normalised (lowercase)
        # email — same user with mixed case must get the same avatar.
        monkeypatch.setattr(
            "rapidly.customers.customer.types.customer.settings.LOGO_DEV_PUBLISHABLE_KEY",
            None,
        )
        lower = _avatar_url("alice@gmail.com")
        upper = _avatar_url("Alice@Gmail.com")
        assert lower == upper

    def test_gravatar_uses_d_404_fallback(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # ``?d=404`` means missing Gravatars return 404, not a
        # stock "mystery person" image. Pinning this prevents a
        # regression that would put identicon placeholders on
        # every customer without a Gravatar.
        monkeypatch.setattr(
            "rapidly.customers.customer.types.customer.settings.LOGO_DEV_PUBLISHABLE_KEY",
            None,
        )
        url = _avatar_url("alice@gmail.com")
        assert url.endswith("?d=404")


class TestAvatarUrlLogoDevPath:
    def test_business_email_uses_logo_dev(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(
            "rapidly.customers.customer.types.customer.settings.LOGO_DEV_PUBLISHABLE_KEY",
            "pk_123",
        )
        url = _avatar_url("cto@acme.com")
        assert "img.logo.dev" in url
        assert "acme.com" in url
        # Pin the key-in-URL contract so we notice if logo.dev
        # changes auth mechanism (query param → header) silently.
        assert "token=pk_123" in url
        # ``fallback=404`` ensures 404 instead of placeholder for
        # unknown companies.
        assert "fallback=404" in url


class TestCustomerWithMembers:
    def test_members_defaults_to_empty_list(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(
            "rapidly.customers.customer.types.customer.settings.LOGO_DEV_PUBLISHABLE_KEY",
            None,
        )
        body = CustomerWithMembers.model_validate(
            {
                "id": uuid4(),
                "created_at": "2026-01-01T00:00:00+00:00",
                "modified_at": "2026-01-01T00:00:00+00:00",
                "external_id": None,
                "email": "c@test.com",
                "email_verified": False,
                "type": None,
                "name": None,
                "billing_address": None,
                "workspace_id": uuid4(),
                "deleted_at": None,
                "metadata": {},
            }
        )
        assert body.members == []
