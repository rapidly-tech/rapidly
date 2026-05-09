"""Utilities for irreversibly anonymising PII before hard deletion."""

from __future__ import annotations

import hashlib

_ANON_EMAIL_DOMAIN = "redacted.invalid"


def sha256_digest(value: str) -> str:
    """Return a hex SHA-256 hash of *value*."""
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


# Keep old name as public alias for callers that import it.
anonymize_for_deletion = sha256_digest

ANONYMIZED_EMAIL_DOMAIN = _ANON_EMAIL_DOMAIN


def anonymize_email_for_deletion(email: str) -> str:
    """Replace an email address with its SHA-256 hash at a non-routable domain."""
    assert "@" in email, f"Expected an email address, got: {email!r}"
    return f"{sha256_digest(email)}@{_ANON_EMAIL_DOMAIN}"
