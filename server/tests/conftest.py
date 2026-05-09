"""Root pytest configuration for the Rapidly test suite."""

import os

# Force the testing environment before any application code is imported.
os.environ["RAPIDLY_ENV"] = "testing"

from tests.fixtures import *  # noqa
import pytest


def pytest_configure(config: pytest.Config) -> None:
    """Register custom markers used across the test suite."""
    config.addinivalue_line(
        "markers",
        "keep_session_state: Disable automatic session clearing before HTTP requests (legacy tests only)",
    )
