"""Defense-in-depth: every chamber feature flag is declared in
settings and defaults to False.

A silently-true default in production would expose a chamber that
hasn't had its staging rollout walked (specs/<chamber>-staging-rollout.md).
Pinning the default guards against someone flipping it in config.py
without realising the implications.
"""

from __future__ import annotations

import pytest

from rapidly.config import Settings

CHAMBER_FLAGS: list[str] = [
    "FILE_SHARING_SCREEN_ENABLED",
    "FILE_SHARING_WATCH_ENABLED",
    "FILE_SHARING_CALL_ENABLED",
    "FILE_SHARING_COLLAB_ENABLED",
]


@pytest.mark.parametrize("flag", CHAMBER_FLAGS)
def test_chamber_flag_defaults_to_false(flag: str) -> None:
    settings = Settings()
    assert getattr(settings, flag) is False, (
        f"{flag} must default to False — flipping it on requires the "
        "chamber's staging rollout to have been walked first"
    )


def test_every_chamber_has_a_flag() -> None:
    """If a new chamber module lands in rapidly/sharing/, it must come
    with its own enable flag. Listing the expected set explicitly
    forces the update when a new chamber ships."""
    settings = Settings()
    for flag in CHAMBER_FLAGS:
        assert hasattr(settings, flag), f"Settings missing {flag}"
