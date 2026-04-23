"""Tests for ``rapidly/platform/search/types.py``.

``SearchResult`` is a discriminated union on ``type`` (share /
customer). The discriminator lets Pydantic dispatch directly to the
correct branch — plain-union fallback would attempt both variants and
produce worse error messages + slower validation on the dashboard
global search endpoint.

Pins also the per-variant ``type`` literal defaults so in-code
constructors don't have to set the discriminator manually.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from rapidly.platform.search.types import (
    SearchResultCustomer,
    SearchResultProduct,
    SearchResults,
    SearchResultTypeAdapter,
)


class TestSearchResultProduct:
    def test_type_default(self) -> None:
        # ``type="share"`` is the literal-default so code calls
        # don't have to set it. Regression that drops the default
        # would break every internal caller constructing shares.
        r = SearchResultProduct(
            id="550e8400-e29b-41d4-a716-446655440000",  # type: ignore[arg-type]
            name="Report.pdf",
        )
        assert r.type == "share"

    def test_description_is_optional(self) -> None:
        r = SearchResultProduct(
            id="550e8400-e29b-41d4-a716-446655440000",  # type: ignore[arg-type]
            name="Report.pdf",
        )
        assert r.description is None


class TestSearchResultCustomer:
    def test_type_default(self) -> None:
        r = SearchResultCustomer(
            id="550e8400-e29b-41d4-a716-446655440000",  # type: ignore[arg-type]
            name="Alice",
            email="alice@test.com",
        )
        assert r.type == "customer"

    def test_email_is_required(self) -> None:
        # ``email`` is required on the customer branch but ``name``
        # is nullable — pin the asymmetry so a silent "fix" making
        # email optional doesn't break the dashboard row rendering.
        with pytest.raises(ValidationError):
            SearchResultCustomer.model_validate(
                {"id": "550e8400-e29b-41d4-a716-446655440000", "name": "x"}
            )

    def test_name_is_nullable(self) -> None:
        r = SearchResultCustomer.model_validate(
            {
                "id": "550e8400-e29b-41d4-a716-446655440000",
                "name": None,
                "email": "alice@test.com",
            }
        )
        assert r.name is None


class TestSearchResultDiscriminator:
    def test_dispatches_to_share_branch(self) -> None:
        r = SearchResultTypeAdapter.validate_python(
            {
                "type": "share",
                "id": "550e8400-e29b-41d4-a716-446655440000",
                "name": "x",
            }
        )
        assert isinstance(r, SearchResultProduct)

    def test_dispatches_to_customer_branch(self) -> None:
        r = SearchResultTypeAdapter.validate_python(
            {
                "type": "customer",
                "id": "550e8400-e29b-41d4-a716-446655440000",
                "name": "x",
                "email": "a@b",
            }
        )
        assert isinstance(r, SearchResultCustomer)

    def test_unknown_type_is_rejected(self) -> None:
        with pytest.raises(ValidationError):
            SearchResultTypeAdapter.validate_python(
                {
                    "type": "workspace",  # not in {"share", "customer"}
                    "id": "550e8400-e29b-41d4-a716-446655440000",
                    "name": "x",
                }
            )


class TestSearchResults:
    def test_empty_results_are_valid(self) -> None:
        # The dashboard global-search endpoint can return an empty
        # list; the envelope must accept it.
        body = SearchResults(results=[])
        assert body.results == []
