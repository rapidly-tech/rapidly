"""Tests for ``rapidly/posthog.py``.

PostHog analytics. Three load-bearing surfaces:

- ``_format_event_name`` produces ``backend:{category}:{noun}:{verb}``
  — the wire-format string PostHog dashboards filter on. A rename
  silently breaks every dashboard funnel.
- ``Service.configure`` is environment-aware: missing API key →
  no client; testing env → client.disabled=True. Without these,
  test runs would ship fake events to the prod PostHog project.
- ``capture`` is a no-op when ``client is None`` so callers can
  unconditionally invoke without guarding (the configure-or-noop
  contract).
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from rapidly.posthog import (
    WORKSPACE_EVENT_DISTINCT_ID,
    Service,
    _extract_signup_attrs,
    _format_event_name,
    configure_posthog,
    posthog,
)


class TestFormatEventName:
    def test_wire_format(self) -> None:
        # Wire-format pin: ``backend:`` prefix distinguishes server-
        # side events from client-side analytics. PostHog dashboards
        # group on this string.
        assert (
            _format_event_name("user", "session", "create")
            == "backend:user:session:create"
        )

    def test_uses_colons_not_dots(self) -> None:
        # PostHog supports any string but our dashboards filter on
        # ``:`` separators specifically. A regression to ``.``
        # would silently drop events from existing dashboards.
        result = _format_event_name("workspaces", "member", "invite")
        assert result.count(":") == 3
        assert "." not in result


class TestExtractSignupAttrs:
    def test_returns_empty_dict_when_no_attribution(self) -> None:
        user = SimpleNamespace(signup_attribution=None)
        assert _extract_signup_attrs(user) == {}  # type: ignore[arg-type]

    def test_prefixes_keys_with_signup(self) -> None:
        # ``signup_`` prefix prevents collision with other event
        # properties — a regression dropping the prefix would let
        # an attribution ``utm_source`` overwrite an event-level
        # ``utm_source``.
        user = SimpleNamespace(
            signup_attribution={"utm_source": "twitter", "intent": "creator"}
        )
        result = _extract_signup_attrs(user)  # type: ignore[arg-type]
        assert result == {
            "signup_utm_source": "twitter",
            "signup_intent": "creator",
        }


class TestWorkspaceDistinctId:
    def test_pinned_value(self) -> None:
        # Workspace-scoped events use a fixed distinct_id so they
        # group under the workspace entity in PostHog. A rename
        # would orphan workspace events from existing user
        # journeys in the dashboard.
        assert WORKSPACE_EVENT_DISTINCT_ID == "workspace_event"


class TestServiceConfigure:
    def test_no_api_key_yields_none_client(
        self,
        monkeypatch: object,
    ) -> None:
        svc = Service()
        with patch("rapidly.posthog.settings.POSTHOG_PROJECT_API_KEY", None):
            svc.configure()
        assert svc.client is None

    def test_with_api_key_creates_client(self) -> None:
        svc = Service()
        with (
            patch("rapidly.posthog.settings.POSTHOG_PROJECT_API_KEY", "phc_test"),
            patch("rapidly.posthog.settings.is_testing", return_value=False),
            patch("rapidly.posthog.settings.POSTHOG_DEBUG", False),
            patch("rapidly.posthog.Posthog") as PosthogCls,
        ):
            svc.configure()
        PosthogCls.assert_called_once_with("phc_test")
        assert svc.client is not None

    def test_disabled_in_testing_env(self) -> None:
        # Load-bearing pin. ``client.disabled = True`` short-circuits
        # every capture; without it, test runs would ship fake events
        # to the prod PostHog project.
        svc = Service()
        with (
            patch("rapidly.posthog.settings.POSTHOG_PROJECT_API_KEY", "phc_test"),
            patch("rapidly.posthog.settings.is_testing", return_value=True),
            patch("rapidly.posthog.settings.POSTHOG_DEBUG", False),
            patch("rapidly.posthog.Posthog") as PosthogCls,
        ):
            svc.configure()
        client = PosthogCls.return_value
        # ``client.disabled = True`` was assigned.
        assert client.disabled is True


class TestCaptureNoOp:
    def test_returns_silently_when_client_is_none(self) -> None:
        # Callers can invoke ``capture`` unconditionally without
        # guarding — the helper is a no-op when no client is
        # configured (dev environment without a key).
        svc = Service()
        svc.client = None
        # Must not raise.
        svc.capture("some-id", "event:noun:verb")


class TestCaptureMergesProperties:
    def test_merges_env_and_caller_props(self) -> None:
        svc = Service()
        client = MagicMock()
        svc.client = client
        with patch(
            "rapidly.posthog.Service._env_properties",
            return_value={"_environment": "testing"},
        ):
            svc.capture(
                "u1", "evt", properties={"foo": "bar"}, groups={"workspace": "w1"}
            )
        client.capture.assert_called_once()
        kwargs = client.capture.call_args.kwargs
        assert kwargs["distinct_id"] == "u1"
        assert kwargs["groups"] == {"workspace": "w1"}
        # env merged with caller props.
        assert kwargs["properties"]["_environment"] == "testing"
        assert kwargs["properties"]["foo"] == "bar"

    def test_caller_props_override_env_props(self) -> None:
        # Same merge semantics as the rest of the codebase: caller-
        # supplied keys WIN over defaults. Pinning protects against
        # a regression that flipped the spread order.
        svc = Service()
        svc.client = MagicMock()
        with patch(
            "rapidly.posthog.Service._env_properties",
            return_value={"_environment": "prod"},
        ):
            svc.capture("u1", "evt", properties={"_environment": "override"})
        kwargs = svc.client.capture.call_args.kwargs
        assert kwargs["properties"]["_environment"] == "override"


class TestAnonymousEventDistinctId:
    def test_uses_rapidly_anonymous(self) -> None:
        # Pinning the literal so the PostHog "anonymous backend
        # events" dashboard funnel keeps grouping correctly.
        svc = Service()
        svc.client = MagicMock()
        with patch(
            "rapidly.posthog.Service._env_properties",
            return_value={"_environment": "testing"},
        ):
            svc.anonymous_event("user", "page", "view")
        kwargs = svc.client.capture.call_args.kwargs
        assert kwargs["distinct_id"] == "rapidly_anonymous"


class TestAuthSubjectEventDispatch:
    def _make_svc(self) -> Service:
        svc = Service()
        svc.client = MagicMock()
        return svc

    def test_user_principal_routes_to_user_event(self) -> None:
        svc = self._make_svc()
        principal = MagicMock()
        with (
            patch("rapidly.posthog.is_user_principal", return_value=True),
            patch.object(svc, "user_event") as ue,
        ):
            svc.auth_subject_event(principal, "user", "page", "view")
        ue.assert_called_once()

    def test_workspace_principal_routes_to_workspace_event(self) -> None:
        svc = self._make_svc()
        principal = MagicMock()
        with (
            patch("rapidly.posthog.is_user_principal", return_value=False),
            patch("rapidly.posthog.is_workspace_principal", return_value=True),
            patch.object(svc, "workspace_event") as we,
        ):
            svc.auth_subject_event(principal, "user", "page", "view")
        we.assert_called_once()

    def test_anonymous_falls_through_to_anonymous_event(self) -> None:
        svc = self._make_svc()
        principal = MagicMock()
        with (
            patch("rapidly.posthog.is_user_principal", return_value=False),
            patch("rapidly.posthog.is_workspace_principal", return_value=False),
            patch.object(svc, "anonymous_event") as ae,
        ):
            svc.auth_subject_event(principal, "user", "page", "view")
        ae.assert_called_once()


class TestModuleSingleton:
    def test_singleton_exists(self) -> None:
        assert isinstance(posthog, Service)

    def test_configure_posthog_calls_configure(self) -> None:
        # Bootstraps the singleton from settings — pin the wiring
        # so the import-time call in app.py still works after
        # refactor.
        with patch.object(posthog, "configure") as configure:
            configure_posthog()
        configure.assert_called_once()
