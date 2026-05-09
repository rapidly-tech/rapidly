"""Conftest for observability tests - isolated from main fixtures.

These tests are designed to run in isolation without requiring the full
Rapidly infrastructure (database, Minio, Redis, etc.). We override the
session-scoped autouse fixtures from the main test suite to prevent
connection attempts.
"""

import os
import tempfile
from collections.abc import Generator
from typing import Any

import pytest

# Set up test environment before any rapidly imports
os.environ["RAPIDLY_ENV"] = "testing"


@pytest.fixture(scope="session", autouse=True)
def setup_prometheus_test_env(tmp_path_factory: pytest.TempPathFactory) -> None:
    """Set up prometheus multiprocess directory for all tests."""
    prom_dir = tmp_path_factory.mktemp("prometheus_multiproc")
    os.environ["PROMETHEUS_MULTIPROC_DIR"] = str(prom_dir)


@pytest.fixture(autouse=True)
def _isolate_prometheus_multiproc_dir() -> Generator[None, None, None]:
    """Per-test ``PROMETHEUS_MULTIPROC_DIR`` isolation.

    ``test_http_middleware.py`` opens its own ``TemporaryDirectory``
    and points the env var at it. When the with-block exits the dir
    is torn down BUT the env var is left pointing at the deleted
    path. Subsequent gauge writes (any test that touches Prometheus
    instruments — security_metrics, slo, otel_prometheus) then
    crash with FileNotFoundError on the mmap dict.

    This fixture wraps each test in its own valid tmp dir AND
    restores the previous value on teardown, breaking the
    poisoning chain across tests.
    """
    with tempfile.TemporaryDirectory() as tmp:
        original = os.environ.get("PROMETHEUS_MULTIPROC_DIR")
        os.environ["PROMETHEUS_MULTIPROC_DIR"] = tmp
        try:
            yield
        finally:
            if original is None:
                os.environ.pop("PROMETHEUS_MULTIPROC_DIR", None)
            else:
                os.environ["PROMETHEUS_MULTIPROC_DIR"] = original


@pytest.fixture(scope="session", autouse=True)
def empty_test_bucket(worker_id: str) -> Any:
    """Override the main test bucket fixture to avoid Minio connections.

    The observability tests don't need S3/Minio access.
    """
    return None


@pytest.fixture(scope="session", autouse=True)
def initialize_test_database(worker_id: str) -> None:
    """Override the main database fixture to avoid PostgreSQL connections.

    The observability tests don't need database access.
    """
    return None


@pytest.fixture(autouse=True)
def patch_middlewares() -> None:
    """Override the main worker middleware fixture.

    The observability tests don't need worker middleware patching.
    """
    pass


@pytest.fixture(autouse=True)
def set_job_queue_manager_context() -> None:
    """Override the main job queue manager fixture.

    The observability tests don't need the job queue manager.
    """
    pass


@pytest.fixture(autouse=True)
def current_message() -> Any:
    """Override the main current message fixture.

    The observability tests don't need dramatiq messages.
    """
    return None
