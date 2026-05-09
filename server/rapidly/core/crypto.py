"""Cryptographic token generation and verification for Rapidly.

Tokens are built from 32 bytes of OS entropy with a 4-byte BLAKE2b
integrity tag, encoded as URL-safe base64.  Storage hashes use keyed
BLAKE2b (faster than HMAC-SHA256, with native keying support).
"""

from __future__ import annotations

import base64
import hashlib
import os

# Layout constants for the raw token body.
_ENTROPY_SIZE = 32
_TAG_SIZE = 4


def _keyed_blake2b(data: bytes, *, key: bytes, digest_size: int = 32) -> bytes:
    return hashlib.blake2b(data, key=key, digest_size=digest_size).digest()


def _integrity_tag(payload: bytes) -> bytes:
    return hashlib.blake2b(payload, digest_size=_TAG_SIZE).digest()


# -- Token hashing (for DB storage) ------------------------------------------


def get_token_hash(token: str, *, secret: str) -> str:
    """Derive a hex-encoded keyed BLAKE2b hash suitable for DB storage.

    The raw *token* is shown to the user once; only this hash is persisted.
    """
    return _keyed_blake2b(token.encode(), key=secret.encode()).hex()


# -- Token generation ---------------------------------------------------------


def generate_token(*, prefix: str = "") -> str:
    """Create a new random token with an embedded integrity check.

    The returned string is ``prefix`` followed by a base64url encoding of
    ``entropy || blake2b_tag``.
    """
    entropy = os.urandom(_ENTROPY_SIZE)
    tag = _integrity_tag(entropy)
    encoded = base64.urlsafe_b64encode(entropy + tag).rstrip(b"=").decode("ascii")
    return f"{prefix}{encoded}"


def _pad_b64(s: str) -> str:
    """Add back the stripped base64 padding."""
    remainder = len(s) % 4
    return s + "=" * ((4 - remainder) % 4)


# -- Convenience pair generation ----------------------------------------------


def generate_token_hash_pair(*, secret: str, prefix: str = "") -> tuple[str, str]:
    """Return ``(raw_token, hash)`` — persist only the hash."""
    token = generate_token(prefix=prefix)
    return token, get_token_hash(token, secret=secret)
