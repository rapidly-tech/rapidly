"""Tests for ``rapidly/messaging/email_update/types.py``.

``EmailUpdateRequest.return_to`` runs through ``get_safe_return_url``
as a ``@field_validator``. That is the **open-redirect defence** on
the email-change flow: the confirmation email's URL is derived from
this value, so an unvalidated input would let a caller enrol their
real email address but arm the confirmation link to bounce the user
through an attacker-controlled origin.

Pinning the validator at schema-construction time — not only at
rendering time — catches any refactor that drops the validator.
"""

from __future__ import annotations

import pytest

from rapidly.messaging.email_update.types import EmailUpdateRequest


class TestReturnToSafety:
    def test_none_falls_back_to_default_frontend_url(self) -> None:
        # A missing return_to must resolve to a safe default, not
        # stay as None — otherwise the email template would render
        # ``?return_to=None`` in the confirmation URL.
        req = EmailUpdateRequest(email="alice@test.com", return_to=None)
        assert req.return_to is not None
        assert req.return_to != ""

    def test_offsite_url_is_rejected_to_default(self) -> None:
        # The hostile case: attacker supplies ``https://evil.test``
        # and the confirmation email ends up bouncing the victim
        # through their origin. ``get_safe_return_url`` must fall
        # back to the canonical frontend URL on any host not in
        # ``settings.ALLOWED_HOSTS``.
        req = EmailUpdateRequest(
            email="alice@test.com", return_to="https://evil.test/steal"
        )
        # The sanitised URL must NOT be the hostile input.
        assert req.return_to is not None
        assert "evil.test" not in req.return_to

    def test_allowed_bare_path_is_preserved(self) -> None:
        # A bare path is legitimate — a dashboard deep-link back to
        # "Settings → Account" is common. ``get_safe_return_url``
        # prefixes the frontend origin.
        req = EmailUpdateRequest(email="alice@test.com", return_to="/settings/account")
        assert req.return_to is not None
        assert req.return_to.endswith("/settings/account")


class TestEmailDnsValidation:
    # EmailStrDNS rejects syntactically-invalid emails. (Deliverability
    # checks are mocked off in tests via ``email_validator.TEST_ENVIRONMENT``.)
    def test_rejects_obviously_invalid_email(self) -> None:
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            EmailUpdateRequest(email="not-an-email", return_to=None)

    def test_accepts_well_formed_email(self) -> None:
        req = EmailUpdateRequest(email="alice@test.com", return_to=None)
        assert req.email == "alice@test.com"
