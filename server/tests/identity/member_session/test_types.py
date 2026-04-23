"""Tests for ``rapidly/identity/member_session/types.py``.

``MemberSession`` carries a ``token`` field with
``validation_alias="raw_token"`` — the SQLAlchemy model exposes the
pre-hashed raw token only on creation (via the named attribute
``raw_token``), and this alias lets the read model surface it on the
response once, immediately after mint. A rename of either side
breaks the single-shot token-delivery contract.

``MemberSessionCreate.return_url`` is typed ``HttpUrl | None`` — the
customer portal renders this as a back button; persisting an
unvalidated URL would let a malicious caller slip ``javascript:`` or
a non-http(s) scheme into the portal's anchor tag.
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from pydantic import ValidationError

from rapidly.identity.member_session.types import (
    MemberSession,
    MemberSessionCreate,
)


class TestMemberSessionCreate:
    def test_requires_member_id(self) -> None:
        with pytest.raises(ValidationError):
            MemberSessionCreate.model_validate({})

    def test_return_url_is_optional(self) -> None:
        body = MemberSessionCreate(member_id=uuid4())
        assert body.return_url is None

    def test_return_url_rejects_non_http_scheme(self) -> None:
        # HttpUrl enforces http(s). A regression to str would let a
        # ``javascript:`` URL persist and be rendered as the portal's
        # back-button anchor.
        with pytest.raises(ValidationError):
            MemberSessionCreate.model_validate(
                {"member_id": str(uuid4()), "return_url": "javascript:alert(1)"}
            )

    def test_return_url_rejects_bare_path(self) -> None:
        # HttpUrl requires a host; bare paths fail. Relative URLs in
        # portal rendering would be ambiguous — the validator defers
        # to the caller to resolve the origin explicitly.
        with pytest.raises(ValidationError):
            MemberSessionCreate.model_validate(
                {"member_id": str(uuid4()), "return_url": "/account"}
            )

    def test_accepts_valid_https_url(self) -> None:
        body = MemberSessionCreate.model_validate(
            {
                "member_id": str(uuid4()),
                "return_url": "https://customer.example/account",
            }
        )
        assert body.return_url is not None
        assert str(body.return_url).startswith("https://")


class TestMemberSessionValidationAlias:
    def test_token_field_uses_raw_token_alias(self) -> None:
        # Pin the alias so a rename on either side breaks here. The
        # SQLAlchemy ``MemberSession`` exposes ``raw_token`` only on
        # creation; the API must read from that attribute to surface
        # the token on the response once.
        field = MemberSession.model_fields["token"]
        assert field.validation_alias == "raw_token"
