"""Tests for ``rapidly/rate_limit.py``.

ASGI rate-limiting middleware configuration. Three load-bearing
surfaces:

- Per-route Rule sets (login-code, file-sharing endpoints) — these
  bound abuse on the file-sharing surface; loosening them
  silently is a brute-force / scanning surface widening
- Production rules > Sandbox rules in throttle limits — sandbox
  is a public-test environment that needs tighter caps to
  discourage automated abuse, prod has higher legit-traffic
  budget. A regression flipping them would either rate-limit
  prod customers or let sandbox abuse drain capacity
- ``get_middleware`` env-based dispatch: production → production
  rules; sandbox/test → sandbox rules; dev/testing → empty (no
  rate-limiting in test runs)
"""

from __future__ import annotations

from typing import Any
from unittest.mock import patch

from rapidly.config import Environment
from rapidly.rate_limit import (
    _BASE_RULES,
    _PRODUCTION_RULES,
    _SANDBOX_RULES,
    get_middleware,
)


async def _fake_app(scope: Any, receive: Any, send: Any) -> None:
    """ASGI app stub used for ``get_middleware`` construction tests."""
    return None


class TestBaseRulesCoverage:
    def test_login_code_endpoint_rate_limited(self) -> None:
        # Brute-force defence on email-based OTP login.
        assert any("login-code" in p for p in _BASE_RULES.keys())

    def test_file_sharing_password_attempt_endpoint(self) -> None:
        # Critical brute-force defence: password-protected file
        # share endpoints must be rate-limited; without it,
        # attackers can grind passwords.
        assert any(
            "file-sharing/channels/.+/password-attempt" in p for p in _BASE_RULES.keys()
        )

    def test_file_sharing_create_endpoint_rate_limited(self) -> None:
        # Spam defence on share creation.
        assert any("file-sharing/channels$" in p for p in _BASE_RULES.keys())

    def test_customer_portal_session_authenticate_rate_limited(self) -> None:
        # OTP brute-force defence on the customer portal login.
        assert any("customer-session" in p for p in _BASE_RULES.keys())


class TestProductionVsSandbox:
    def test_sandbox_has_tighter_v1_limits(self) -> None:
        # Sandbox is publicly accessible; tighter caps discourage
        # automated abuse. A regression flipping prod / sandbox
        # would either rate-limit prod customers or let sandbox
        # abuse drain capacity.
        sandbox_v1 = _SANDBOX_RULES["^/v1"]
        prod_v1 = _PRODUCTION_RULES["^/v1"]
        # Compare the ``default`` group's per-minute cap.
        sandbox_default = next(r for r in sandbox_v1 if "default" in str(r.group))
        prod_default = next(r for r in prod_v1 if "default" in str(r.group))
        assert sandbox_default.minute < prod_default.minute  # type: ignore[operator]

    def test_both_envs_inherit_base_rules(self) -> None:
        # Per-route rules from ``_BASE_RULES`` apply in both prod
        # and sandbox; only the catch-all ``/v1`` rule differs.
        for path in _BASE_RULES.keys():
            assert path in _SANDBOX_RULES
            assert path in _PRODUCTION_RULES

    def test_v1_rules_cover_every_rate_limit_group(self) -> None:
        # The catch-all ``/v1`` block must enumerate every
        # ``RateLimitGroup`` so no group falls through unmatched.
        from rapidly.enums import RateLimitGroup

        prod_groups = {r.group for r in _PRODUCTION_RULES["^/v1"]}
        # Every defined group should appear (or its equivalent).
        for group in (
            RateLimitGroup.restricted,
            RateLimitGroup.default,
            RateLimitGroup.web,
            RateLimitGroup.elevated,
        ):
            assert group in prod_groups


class TestGetMiddlewareDispatch:
    def test_production_uses_production_rules(self) -> None:

        with (
            patch("rapidly.rate_limit.settings.ENV", Environment.production),
            patch("rapidly.rate_limit.create_redis"),
            patch("rapidly.rate_limit.RateLimitMiddleware") as MW,
        ):
            get_middleware(_fake_app)
        # The 4th positional arg to RateLimitMiddleware is the rules dict.
        call_args = MW.call_args
        rules = (
            call_args.args[3]
            if len(call_args.args) > 3
            else call_args.kwargs.get("config")
        )
        assert rules is _PRODUCTION_RULES

    def test_sandbox_uses_sandbox_rules(self) -> None:
        with (
            patch("rapidly.rate_limit.settings.ENV", Environment.sandbox),
            patch("rapidly.rate_limit.create_redis"),
            patch("rapidly.rate_limit.RateLimitMiddleware") as MW,
        ):
            get_middleware(_fake_app)
        rules = MW.call_args.args[3]
        assert rules is _SANDBOX_RULES

    def test_test_env_uses_sandbox_rules(self) -> None:
        # The hosted Hetzner staging env (Environment.test) shares
        # rules with sandbox — both are public-test envs.
        with (
            patch("rapidly.rate_limit.settings.ENV", Environment.test),
            patch("rapidly.rate_limit.create_redis"),
            patch("rapidly.rate_limit.RateLimitMiddleware") as MW,
        ):
            get_middleware(_fake_app)
        rules = MW.call_args.args[3]
        assert rules is _SANDBOX_RULES

    def test_development_uses_empty_rules(self) -> None:
        # Dev env has NO rate limiting — local iteration would be
        # painfully slow if every request had to pass through the
        # Redis bucket check.
        with (
            patch("rapidly.rate_limit.settings.ENV", Environment.development),
            patch("rapidly.rate_limit.create_redis"),
            patch("rapidly.rate_limit.RateLimitMiddleware") as MW,
        ):
            get_middleware(_fake_app)
        rules = MW.call_args.args[3]
        assert rules == {}

    def test_testing_uses_empty_rules(self) -> None:
        # Local pytest runner — no rate limiting (would make tests
        # flaky).
        with (
            patch("rapidly.rate_limit.settings.ENV", Environment.testing),
            patch("rapidly.rate_limit.create_redis"),
            patch("rapidly.rate_limit.RateLimitMiddleware") as MW,
        ):
            get_middleware(_fake_app)
        rules = MW.call_args.args[3]
        assert rules == {}


class TestSpecificRules:
    def test_login_code_minute_cap_is_6(self) -> None:
        # Pin the documented brute-force budget on the OTP login
        # endpoint. Loosening would speed up brute-force on 6-digit
        # codes; the matching ``check_otp_rate_limit`` Redis budget
        # is also 10/15min (Phase 124).
        for path, rules in _BASE_RULES.items():
            if "login-code" in path:
                rule = rules[0]
                assert rule.minute == 6
                return
        raise AssertionError("login-code rule not found")

    def test_password_attempt_minute_cap_is_15(self) -> None:
        # Per-share password-attempt budget — prevents brute-force
        # on a single share's password.
        for path, rules in _BASE_RULES.items():
            if "password-attempt" in path:
                rule = rules[0]
                assert rule.minute == 15
                return
        raise AssertionError("password-attempt rule not found")


class TestExports:
    def test_get_middleware_exported(self) -> None:
        from rapidly import rate_limit as M

        assert M.__all__ == ["get_middleware"]
