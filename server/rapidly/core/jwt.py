"""Thin wrapper around PyJWT for signed, typed tokens.

Each token carries a ``type`` claim (stored as the JWT ``aud`` field) so that
a token minted for one purpose (e.g. ``"discord_oauth"``) cannot be replayed
in a context expecting another (e.g. ``"customer_oauth"``).
"""

from __future__ import annotations

from typing import Any

import jwt as _jwt
from jwt import DecodeError, ExpiredSignatureError

__all__ = [
    "DecodeError",
    "ExpiredSignatureError",
    "decode",
    "encode",
]

_ALGORITHM = "HS256"


def encode(*, data: dict[str, Any], secret: str, type: str) -> str:
    """Return a signed JWT embedding *data* with the given *type*."""
    payload = {**data, "aud": type}
    return _jwt.encode(payload, secret, algorithm=_ALGORITHM)


def decode(*, token: str, secret: str, type: str) -> dict[str, Any]:
    """Verify and decode a JWT, requiring *type* as the audience."""
    return _jwt.decode(
        token,
        secret,
        algorithms=[_ALGORITHM],
        audience=type,
    )
