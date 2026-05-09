"""Tests for ``rapidly/identity/oauth2/userinfo.py``.

OIDC UserInfo is what ``/oauth2/userinfo`` returns; every OIDC client
consumes these claims. The module's contract:

- ``sub`` is always present (the stringified subject id)
- User subject: ``email`` + ``email_verified`` ONLY when the ``email``
  scope is granted — preventing PII leak on scope-minimal tokens
- Workspace subject: ``name`` (= slug) ONLY when the ``openid`` scope
  is granted
- Empty scope string returns ``sub`` only — the minimal identity
  fingerprint; a regression that returned more claims would leak data
  the client didn't request
- Unknown subject types raise ``NotImplementedError`` — a defensive
  crash beats a silent all-claims leak
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any, cast
from uuid import uuid4

import pytest

from rapidly.identity.oauth2.sub_type import SubType, SubTypeValue
from rapidly.identity.oauth2.userinfo import generate_user_info


def _user_sub(
    email: str = "alice@test.com", email_verified: bool = True
) -> SubTypeValue:
    user = SimpleNamespace(id=uuid4(), email=email, email_verified=email_verified)
    return cast("SubTypeValue", (SubType.user, user))


def _workspace_sub(slug: str = "acme") -> SubTypeValue:
    workspace = SimpleNamespace(id=uuid4(), slug=slug)
    return cast("SubTypeValue", (SubType.workspace, workspace))


class TestBaseClaim:
    def test_sub_always_present(self) -> None:
        sub = _user_sub()
        info = generate_user_info(sub, scope="")
        assert info["sub"] == str(sub[1].id)

    def test_empty_scope_returns_only_sub(self) -> None:
        # Scope-minimal tokens must only surface the subject id.
        # Pinning prevents a regression that attaches email / slug
        # by default and leaks them without an explicit scope grant.
        sub = _user_sub()
        info = generate_user_info(sub, scope="")
        assert set(info.keys()) == {"sub"}


class TestUserClaims:
    def test_email_scope_surfaces_email_and_verified(self) -> None:
        sub = _user_sub(email="alice@test.com", email_verified=True)
        info = generate_user_info(sub, scope="email")
        assert info["email"] == "alice@test.com"
        assert info["email_verified"] is True

    def test_without_email_scope_no_email_claim(self) -> None:
        # Load-bearing privacy pin: a token without the ``email``
        # scope must NOT surface the email — the same subject id +
        # nothing else. An accidental regression returning email
        # by default would leak PII on minimal-scope tokens
        # (e.g. sign-in-only flows).
        sub = _user_sub()
        info = generate_user_info(sub, scope="openid")
        assert "email" not in info
        assert "email_verified" not in info

    def test_email_scope_alongside_other_scopes(self) -> None:
        sub = _user_sub()
        info = generate_user_info(sub, scope="openid email customer_portal:read")
        assert info["email"] == sub[1].email

    def test_unverified_email_is_surfaced_as_false(self) -> None:
        # email_verified is a bool signal — False must propagate
        # (not be silently elided).
        sub = _user_sub(email_verified=False)
        info = generate_user_info(sub, scope="email")
        assert info["email_verified"] is False


class TestWorkspaceClaims:
    def test_openid_scope_surfaces_name(self) -> None:
        sub = _workspace_sub(slug="acme")
        info = generate_user_info(sub, scope="openid")
        assert info["name"] == "acme"

    def test_without_openid_scope_no_name(self) -> None:
        sub = _workspace_sub()
        info = generate_user_info(sub, scope="customer_portal:read")
        assert "name" not in info

    def test_workspace_does_not_leak_email(self) -> None:
        # Workspace subjects don't have an email attribute — a
        # regression that copied the user path onto workspace would
        # AttributeError. Pinning the workspace claim set prevents
        # that.
        sub = _workspace_sub()
        info = generate_user_info(sub, scope="email openid")
        assert "email" not in info


class TestUnknownSubject:
    def test_unknown_sub_type_raises(self) -> None:
        # SubType only has user / workspace. A future addition
        # without wiring a claim builder must crash loudly, not
        # silently return ``sub`` only — that would look like a
        # successful auth while the scope claims are empty.
        bad: Any = ("customer", SimpleNamespace(id=uuid4()))
        with pytest.raises(NotImplementedError):
            generate_user_info(bad, scope="email")


class TestExports:
    def test_userinfo_and_generate_are_exported(self) -> None:
        from rapidly.identity.oauth2 import userinfo as U

        assert set(U.__all__) == {"UserInfo", "generate_user_info"}
