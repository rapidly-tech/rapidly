"""Tests for ``rapidly/analytics/metrics/permissions.py``.

Pins the scope + subject set on the metrics endpoint. There's no
``MetricsWrite`` — metrics are read-only (computed server-side from
events).
"""

from __future__ import annotations

from fastapi.params import Depends

from rapidly.analytics.metrics import permissions as perms
from rapidly.identity.auth.dependencies import _Authenticator
from rapidly.identity.auth.models import User, Workspace
from rapidly.identity.auth.scope import Scope


def _extract(annotated_type: object) -> _Authenticator:
    meta = annotated_type.__metadata__  # type: ignore[attr-defined]
    dep = meta[0]
    assert isinstance(dep, Depends)
    auth = dep.dependency
    assert isinstance(auth, _Authenticator)
    return auth


class TestMetricsRead:
    def test_allows_user_and_workspace(self) -> None:
        assert _extract(perms.MetricsRead).allowed_subjects == {User, Workspace}

    def test_requires_metrics_read_and_web(self) -> None:
        assert _extract(perms.MetricsRead).required_scopes == {
            Scope.web_read,
            Scope.web_write,
            Scope.metrics_read,
        }

    def test_does_not_include_any_write_scopes(self) -> None:
        # Defensive: metrics are read-only; any ``*_write`` scope in
        # the required set would widen the audience unintentionally.
        auth = _extract(perms.MetricsRead)
        for scope in auth.required_scopes or set():
            # ``web_write`` is an allowed scope because browser
            # sessions include it by default — exclude that one
            # explicitly. Any OTHER write scope would be a regression.
            assert scope == Scope.web_write or not scope.value.endswith(":write")

    def test_module_does_not_export_MetricsWrite(self) -> None:
        # Metrics are computed server-side; there is no write path.
        # Pinning prevents a future refactor from adding a
        # ``MetricsWrite`` alongside the existing ``MetricsRead``
        # without this file being updated.
        assert not hasattr(perms, "MetricsWrite")
