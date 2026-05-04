"""Tests for ``rapidly/identity/login_code/types.py``.

Mirrors the open-redirect defence pinned on ``email_update`` in
Phase 114: ``LoginCodeRequest.return_to`` runs through
``get_safe_return_url`` as a ``@field_validator``. The login-code
email's call-to-action URL is derived from this value, so an
unvalidated input would let an attacker phish by enrolling a victim's
email and arming the login link to bounce them through an
attacker-controlled origin.

Pinning BOTH email-gated flows (email_update AND login_code) catches
a refactor that drops the validator on one but not the other.
"""

from __future__ import annotations

import pytest

from rapidly.identity.login_code.types import LoginCodeRequest


class TestReturnToSafety:
    def test_none_falls_back_to_default(self) -> None:
        req = LoginCodeRequest(email="alice@test.com", return_to=None)
        assert req.return_to is not None
        assert req.return_to != ""

    def test_offsite_url_is_sanitised(self) -> None:
        req = LoginCodeRequest(
            email="alice@test.com", return_to="https://evil.test/steal"
        )
        assert req.return_to is not None
        assert "evil.test" not in req.return_to

    def test_allowed_bare_path_is_preserved(self) -> None:
        req = LoginCodeRequest(email="alice@test.com", return_to="/dashboard")
        assert req.return_to is not None
        assert req.return_to.endswith("/dashboard")


class TestLoginCodeBodyShape:
    def test_rejects_invalid_email(self) -> None:
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            LoginCodeRequest(email="not-an-email", return_to=None)

    def test_attribution_is_optional(self) -> None:
        req = LoginCodeRequest(email="alice@test.com", return_to=None)
        assert req.attribution is None
