"""Unit tests for ``rapidly/openapi.py``.

Complements ``test_openapi.py`` (a route-level smoke test that hits
``/openapi.json``) with pure-unit pins on the schema-pipeline
internals:

- ``APITag`` controls per-endpoint visibility (public / private / mcp).
  The routing module's ``SchemaInclusionRoute`` reads these tags to
  decide ``include_in_schema`` (Phase 108).
- ``_apply_transformers`` composes schema-mutating callables in
  sequence — order is the pipeline definition order; reversing it
  would let a later transformer's output be overwritten.
- ``set_openapi_generator`` memoises on ``app.openapi_schema`` so
  per-request ``/openapi.json`` doesn't rebuild and re-walk every
  route on every call (multi-second latency on large apps).
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

from rapidly.openapi import (
    OPENAPI_PARAMETERS,
    APITag,
    _apply_transformers,
    _load_transformers,
    set_openapi_generator,
)


class TestAPITag:
    def test_three_values(self) -> None:
        # 3 buckets: public (docs), private (dashboard), mcp.
        # Adding a 4th bucket without wiring SchemaInclusionRoute
        # would render new endpoints in unexpected views.
        assert {e.value for e in APITag} == {"public", "private", "mcp"}

    def test_metadata_describes_every_tag(self) -> None:
        # The metadata dict surfaces in the OpenAPI ``tags`` array;
        # missing entries leave a tag undocumented in the spec.
        names = [m["name"] for m in APITag.metadata()]
        assert sorted(names) == sorted([t.value for t in APITag])

    def test_metadata_entries_have_description(self) -> None:
        for entry in APITag.metadata():
            assert "description" in entry
            assert isinstance(entry["description"], str)
            assert len(entry["description"]) > 0


class TestOpenAPIParameters:
    def test_title_pinned(self) -> None:
        # Title appears on the docs landing page; drift desyncs
        # public-facing branding.
        assert OPENAPI_PARAMETERS["title"] == "Rapidly API"

    def test_servers_pinned_to_production(self) -> None:
        # The default ``servers`` array is what curl examples + SDK
        # generators target. A regression to a staging URL would
        # mislead integrators.
        servers = OPENAPI_PARAMETERS["servers"]
        assert len(servers) == 1
        assert servers[0]["url"] == "https://api.rapidly.tech"

    def test_openapi_tags_includes_all_apitags(self) -> None:
        names = {t["name"] for t in OPENAPI_PARAMETERS["openapi_tags"]}
        assert names == {t.value for t in APITag}


class TestLoadTransformers:
    def test_returns_two_callables(self) -> None:
        transformers = _load_transformers()
        # 2 transformers: metadata-query schema + oauth2 form-encoded
        # schemas. Adding a third silently means it doesn't run on
        # the schema unless this module's ``_load_transformers`` is
        # updated.
        assert len(transformers) == 2
        for fn in transformers:
            assert callable(fn)


class TestApplyTransformers:
    def test_each_transformer_runs_in_order(self) -> None:
        # Order matters — a later transformer's mutation can
        # depend on an earlier one's keys.
        order: list[str] = []

        def first(s: dict[str, Any]) -> dict[str, Any]:
            order.append("first")
            s["seq"] = "1"
            return s

        def second(s: dict[str, Any]) -> dict[str, Any]:
            order.append("second")
            s["seq"] += "2"
            return s

        result = _apply_transformers({}, (first, second))
        assert order == ["first", "second"]
        assert result["seq"] == "12"

    def test_empty_transformers_returns_input_unchanged(self) -> None:
        schema = {"a": 1}
        result = _apply_transformers(schema, ())
        assert result == {"a": 1}

    def test_transformer_can_replace_schema(self) -> None:
        # ``functools.reduce`` lets a transformer return a new dict
        # entirely — used for shallow-merging extension dicts.
        result = _apply_transformers({"old": True}, (lambda _s: {"new": True},))
        assert result == {"new": True}


class TestSetOpenAPIGenerator:
    def test_assigns_openapi_callable_on_app(self) -> None:
        app = MagicMock()
        app.openapi_schema = None
        set_openapi_generator(app)
        # ``app.openapi`` must be the generator callable.
        assert callable(app.openapi)

    def test_memoises_after_first_call(self) -> None:
        # Load-bearing pin. Once the schema is built, subsequent
        # calls return the cached dict — without this, every
        # ``/openapi.json`` request would re-walk every route +
        # re-run the transformer pipeline (multi-second latency
        # on a large app).
        cached = {"cached": True}
        app = MagicMock()
        app.openapi_schema = cached
        set_openapi_generator(app)
        assert app.openapi() is cached


class TestExports:
    def test_all_documented(self) -> None:
        from rapidly import openapi as M

        assert set(M.__all__) == {
            "OPENAPI_PARAMETERS",
            "APITag",
            "set_openapi_generator",
        }
