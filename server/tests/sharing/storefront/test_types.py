"""Tests for ``rapidly/sharing/storefront/types.py``.

Public storefront response schemas. Every field is exposed on an
UNAUTHENTICATED endpoint, so the shape is the customer-facing
contract — drift (renamed field, changed currency default, missing
download_count) silently breaks storefront rendering + SEO / OG
scraping.

Pins:
- ``FileShareStorefront`` default values (``currency="usd"``,
  ``download_count=0``) — storefront copies these in the product
  card header
- Nullable fields remain nullable (``title`` / ``file_name`` /
  ``file_size_bytes`` / ``price_cents`` / ``expires_at``) so unset
  shares still render (price-TBD, expiry-never, free-tier)
- ``Storefront`` envelope: ``secrets`` defaults to empty list (not
  required) — old workspaces without secret items must still
  storefront-render
- Required fields stay required (workspace, file_shares, customers)
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from rapidly.sharing.storefront.types import (
    FileShareStorefront,
    SecretStorefront,
    Storefront,
    StorefrontCustomer,
    StorefrontCustomers,
)


class TestFileShareStorefrontDefaults:
    def test_currency_defaults_to_usd(self) -> None:
        # Storefront cards render the currency code in the price
        # label; a silent flip to EUR/GBP would mislabel every card
        # on workspaces that never set a currency explicitly.
        body = FileShareStorefront.model_validate(
            {
                "id": "550e8400-e29b-41d4-a716-446655440000",
                "created_at": "2026-01-01T00:00:00+00:00",
                "modified_at": "2026-01-01T00:00:00+00:00",
                "short_slug": "abc",
            }
        )
        assert body.currency == "usd"

    def test_download_count_defaults_to_zero(self) -> None:
        # Social-proof "N downloads" renderer expects 0 for freshly
        # created shares, not None/missing.
        body = FileShareStorefront.model_validate(
            {
                "id": "550e8400-e29b-41d4-a716-446655440000",
                "created_at": "2026-01-01T00:00:00+00:00",
                "modified_at": "2026-01-01T00:00:00+00:00",
                "short_slug": "abc",
            }
        )
        assert body.download_count == 0

    @pytest.mark.parametrize(
        "field", ["title", "file_name", "file_size_bytes", "price_cents", "expires_at"]
    )
    def test_optional_fields_default_to_none(self, field: str) -> None:
        # Each optional field must default to None so partial
        # records (e.g. still-uploading share) render without 422.
        body = FileShareStorefront.model_validate(
            {
                "id": "550e8400-e29b-41d4-a716-446655440000",
                "created_at": "2026-01-01T00:00:00+00:00",
                "modified_at": "2026-01-01T00:00:00+00:00",
                "short_slug": "abc",
            }
        )
        assert getattr(body, field) is None

    def test_short_slug_is_required(self) -> None:
        # ``short_slug`` builds the public URL — missing is a
        # construction error, not a rendering fallback.
        with pytest.raises(ValidationError):
            FileShareStorefront.model_validate(
                {
                    "id": "550e8400-e29b-41d4-a716-446655440000",
                    "created_at": "2026-01-01T00:00:00+00:00",
                    "modified_at": "2026-01-01T00:00:00+00:00",
                }
            )


class TestSecretStorefront:
    def _base(self, **overrides: object) -> dict[str, object]:
        body: dict[str, object] = {
            "id": "sec_id",
            "created_at": "2026-01-01T00:00:00+00:00",
            "uuid": "550e8400-e29b-41d4-a716-446655440000",
        }
        body.update(overrides)
        return body

    def test_currency_defaults_to_usd(self) -> None:
        body = SecretStorefront.model_validate(self._base())
        assert body.currency == "usd"

    def test_title_and_price_optional(self) -> None:
        body = SecretStorefront.model_validate(self._base())
        assert body.title is None
        assert body.price_cents is None
        assert body.expires_at is None

    def test_uuid_required(self) -> None:
        with pytest.raises(ValidationError):
            SecretStorefront.model_validate(
                {"id": "sec_id", "created_at": "2026-01-01T00:00:00+00:00"}
            )


class TestStorefrontCustomers:
    def test_accepts_empty_list(self) -> None:
        body = StorefrontCustomers(total=0, customers=[])
        assert body.total == 0
        assert body.customers == []

    def test_total_and_customers_required(self) -> None:
        with pytest.raises(ValidationError):
            StorefrontCustomers.model_validate({"customers": []})
        with pytest.raises(ValidationError):
            StorefrontCustomers.model_validate({"total": 0})


class TestStorefrontCustomer:
    def test_name_required(self) -> None:
        with pytest.raises(ValidationError):
            StorefrontCustomer.model_validate({})

    def test_accepts_name(self) -> None:
        body = StorefrontCustomer(name="Alice")
        assert body.name == "Alice"


class TestStorefrontEnvelope:
    def test_secrets_defaults_to_empty_list(self) -> None:
        # Old workspaces don't have secret items; ``secrets`` must
        # default to ``[]`` so the storefront still renders.
        # Construct with a minimal workspace dict via model_validate.
        assert "secrets" in Storefront.model_fields
        field = Storefront.model_fields["secrets"]
        # default_factory pin: factory produces an empty list.
        assert field.default_factory is not None
        assert field.default_factory() == []  # type: ignore[call-arg]

    def test_required_fields(self) -> None:
        # workspace + file_shares + customers are required; a regression
        # making any of them optional would let an empty {} pass and
        # crash downstream template rendering.
        required = {
            name
            for name, field in Storefront.model_fields.items()
            if field.is_required()
        }
        assert required == {"workspace", "file_shares", "customers"}
