"""Slug generation utilities for channel identification."""

import secrets
import uuid

from .wordlist import TOPPINGS

# Configuration constants
# Security: 7 words from 128 word list = 128^7 ~= 5.6 * 10^14 (~49 bits)
# This provides strong entropy against brute-force slug guessing
LONG_SLUG_NUM_WORDS = 7
SLUG_MAX_ATTEMPTS = 8


def generate_short_slug() -> str:
    """Generate a UUID-based slug for secure channel identification.

    Returns:
        A UUID string (36 chars, ~122 bits of entropy)
    """
    return str(uuid.uuid4())


def generate_long_slug() -> str:
    """Generate a human-readable slug from random words.

    Returns:
        A string of random words joined by '/' (7 words from 128-word list, ~49 bits)
    """
    words = [secrets.choice(TOPPINGS) for _ in range(LONG_SLUG_NUM_WORDS)]
    return "/".join(words)


def generate_secret() -> str:
    """Generate a cryptographically secure secret for channel ownership.

    Returns:
        A hex string (64 characters, 256 bits)
    """
    return secrets.token_hex(32)
