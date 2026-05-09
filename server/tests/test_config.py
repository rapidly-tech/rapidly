"""Tests for ``rapidly/config.py``.

Application configuration. The module is large; this file pins the
helpers that don't require a live env (URL builders, environment
predicates, enum membership). Engine factories + secret-loading are
exercised by integration tests that boot a real settings instance.
"""

from __future__ import annotations

import pytest

from rapidly.config import EmailSender, Environment, settings


class TestEnvironmentEnum:
    def test_known_values(self) -> None:
        # Five deployment stages; the env-var ``RAPIDLY_ENV`` only
        # accepts these literals. Adding a new stage silently means
        # callers can't target it via env, AND the predicates
        # ``is_*`` would not have a matching method.
        assert {e.value for e in Environment} == {
            "development",
            "testing",
            "sandbox",
            "production",
            "test",
        }

    def test_test_vs_testing_distinction(self) -> None:
        # Documented distinction: ``testing`` is the local pytest
        # runner; ``test`` is the hosted staging environment on
        # Hetzner. Conflating them would let test-only behaviour
        # leak into staging. Compare via ``.value`` to sidestep
        # mypy's literal-type narrowing.
        assert str(Environment.testing.value) != str(Environment.test.value)


class TestEmailSenderEnum:
    def test_two_transports(self) -> None:
        assert {e.value for e in EmailSender} == {"logger", "gmail"}


class TestEnvironmentPredicates:
    def test_is_environment_set_membership(self) -> None:
        # ``is_environment({a, b})`` is True iff current ENV is in
        # the set. Used by ``is_environment`` callers (e.g. the
        # OPENAPI_PARAMETERS docs-hide check).
        assert settings.is_environment({settings.ENV}) is True
        # Empty set always yields False.
        assert settings.is_environment(set()) is False

    def test_is_testing_matches_env_enum_value(self) -> None:
        # The pytest runner sets ENV=testing.
        assert settings.is_testing() is (settings.ENV is Environment.testing)

    def test_is_development_matches_env_enum_value(self) -> None:
        assert settings.is_development() is (settings.ENV is Environment.development)

    def test_is_sandbox_matches_env_enum_value(self) -> None:
        assert settings.is_sandbox() is (settings.ENV is Environment.sandbox)

    def test_is_production_matches_env_enum_value(self) -> None:
        assert settings.is_production() is (settings.ENV is Environment.production)

    def test_predicates_are_mutually_exclusive(self) -> None:
        # At most one ``is_*`` predicate should ever be True at a
        # time — otherwise behaviour gating becomes ambiguous.
        true_count = sum(
            [
                settings.is_testing(),
                settings.is_development(),
                settings.is_sandbox(),
                settings.is_production(),
            ]
        )
        assert true_count <= 1


class TestUrlBuilders:
    def test_generate_external_url_uses_base_url(self) -> None:
        url = settings.generate_external_url("/foo")
        assert url == f"{settings.BASE_URL}/foo"

    def test_generate_frontend_url_uses_frontend_base_url(self) -> None:
        url = settings.generate_frontend_url("/dashboard")
        assert url == f"{settings.FRONTEND_BASE_URL}/dashboard"

    def test_generate_admin_url_falls_back_to_backend_when_admin_host_unset(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # When ``ADMIN_HOST`` is None, the admin lives at
        # ``{BASE_URL}/admin{path}``. Pin so a regression that
        # always returned the `https://` form would 500 in dev
        # (no ADMIN_HOST set there).
        monkeypatch.setattr(settings, "ADMIN_HOST", None)
        url = settings.generate_admin_url("/customers")
        assert url == f"{settings.BASE_URL}/admin/customers"

    def test_generate_admin_url_uses_admin_host_when_set(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(settings, "ADMIN_HOST", "admin.rapidly.tech")
        url = settings.generate_admin_url("/customers")
        # ``https://`` (NOT ``http://``) — production admin must
        # always be HTTPS.
        assert url == "https://admin.rapidly.tech/customers"


class TestRedisUrl:
    def test_redis_url_proxies_to_cache_config(self) -> None:
        assert settings.redis_url == settings.cache.url


class TestPostgresDsn:
    def test_returns_string_for_asyncpg(self) -> None:
        # The DSN is used by ``create_async_engine``; it must be a
        # str so SQLAlchemy can parse it.
        dsn = settings.get_postgres_dsn("asyncpg")
        assert isinstance(dsn, str)
        assert dsn.startswith("postgresql+asyncpg://")

    def test_returns_string_for_psycopg2(self) -> None:
        dsn = settings.get_postgres_dsn("psycopg2")
        assert isinstance(dsn, str)
        assert dsn.startswith("postgresql+psycopg2://")
