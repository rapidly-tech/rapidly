"""Shared utilities for the file sharing module."""

import hashlib
import hmac

from rapidly.config import settings


def hash_ip(ip: str) -> str:
    """Privacy-preserving IP hash for rate limit keys.

    Uses HMAC-SHA256 with the application secret to prevent rainbow table
    reversal of the IPv4 address space (~4 billion addresses).
    """
    return hmac.new(settings.SECRET.encode(), ip.encode(), hashlib.sha256).hexdigest()[
        :16
    ]
