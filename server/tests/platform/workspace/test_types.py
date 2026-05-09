"""Tests for ``rapidly/platform/workspace/types.py``.

Pins the load-bearing invariants on the workspace types module:

- **Slug reserved-keyword rejection** — workspace slugs double as
  URL prefixes (``/{slug}/...``) on the storefront. Letting a user
  register ``dashboard`` / ``admin`` / ``login`` as a slug would
  shadow the real route and phish visitors who expect those paths.
- **Slug case + charset** — ``SlugValidator`` + ``to_lower=True``
  keep the slug single-canonical.
- **``_discard_logo_dev_url``** — ``logo.dev`` placeholder URLs
  (from the auto-fetched workspace avatar) coerce to None so the
  dashboard doesn't render an inscrutable stock logo.
- **``WorkspaceSocialLink`` cross-domain validation** — a caller
  can't claim ``platform=x`` but hand over a ``facebook.com`` URL
  (or vice versa) to impersonate an unrelated brand on a workspace
  profile.
- **``LegacyWorkspaceStatus`` coalescence** — the SDK-facing status
  collapses INITIAL_REVIEW + ONGOING_REVIEW both into UNDER_REVIEW.
  A regression that surfaced the finer-grained values would break
  SDK consumers reading the coalesced legacy field.
- **``WorkspaceCreate.default_presentment_currency``** defaults to
  ``PresentmentCurrency.usd`` — a silent flip would change the
  default checkout currency.
"""

from __future__ import annotations

import pytest
from pydantic import HttpUrl, ValidationError

from rapidly.config import settings
from rapidly.models.workspace import WorkspaceStatus
from rapidly.platform.workspace.types import (
    LegacyWorkspaceStatus,
    WorkspaceCreate,
    WorkspaceSocialLink,
    WorkspaceSocialPlatforms,
    _discard_logo_dev_url,
    _reject_reserved_slug,
)

# ── Slug reserved-keyword rejection ──


class TestRejectReservedSlug:
    @pytest.mark.parametrize(
        "reserved",
        [
            "dashboard",
            "settings",
            "login",
            "signup",
            "oauth2",
            "admin",
            "file-sharing",
            "share",
            ".well-known",
        ],
    )
    def test_rejects_reserved_keyword(self, reserved: str) -> None:
        with pytest.raises(ValueError, match="reserved"):
            _reject_reserved_slug(reserved)

    def test_accepts_non_reserved(self) -> None:
        assert _reject_reserved_slug("acme-inc") == "acme-inc"

    def test_reserved_list_is_pinned(self) -> None:
        # Pin the exact reserved list — additions must be intentional
        # because every storefront URL-prefix consumer (reverse proxy,
        # Next.js route matcher) must know about them.
        assert set(settings.WORKSPACE_SLUG_RESERVED_KEYWORDS) == {
            "dashboard",
            "settings",
            "login",
            "signup",
            "oauth2",
            "admin",
            "finance",
            "docs",
            "careers",
            "legal",
            ".well-known",
            "file-sharing",
            "download",
            "share",
        }


# ── WorkspaceCreate.slug integration ──


class TestWorkspaceCreateSlugValidation:
    _base: dict[str, object] = {"name": "Acme Inc"}

    def test_rejects_reserved_slug(self) -> None:
        with pytest.raises(ValidationError):
            WorkspaceCreate(name="Acme", slug="admin")

    def test_rejects_uppercase_slug_via_to_lower_coercion(self) -> None:
        # ``StringConstraints(to_lower=True)`` normalises uppercase
        # before the SlugValidator runs, so the canonical form is
        # accepted but ``ACME`` becomes ``acme``.
        body = WorkspaceCreate(name="Acme", slug="ACME")
        assert body.slug == "acme"

    def test_rejects_below_min_length(self) -> None:
        # SHARE_NAME_MIN_LENGTH = 3 — 2-char slug rejected.
        with pytest.raises(ValidationError):
            WorkspaceCreate(name="Acme Inc", slug="ac")


# ── Logo.dev placeholder discard ──


class TestDiscardLogoDevUrl:
    def test_logo_dev_url_becomes_none(self) -> None:
        # Auto-fetched placeholders must NOT reach the dashboard;
        # they'd render a stock logo unrelated to the workspace.
        assert _discard_logo_dev_url(HttpUrl("https://img.logo.dev/acme")) is None

    def test_non_logo_dev_url_passes_through(self) -> None:
        url = HttpUrl("https://cdn.example.com/avatar.png")
        assert _discard_logo_dev_url(url) == url


# ── Social link cross-platform validation ──


class TestWorkspaceSocialLinkValidator:
    @pytest.mark.parametrize(
        ("platform", "good_url"),
        [
            (WorkspaceSocialPlatforms.x, "https://x.com/acme"),
            (WorkspaceSocialPlatforms.x, "https://twitter.com/acme"),
            (WorkspaceSocialPlatforms.github, "https://github.com/acme"),
            (WorkspaceSocialPlatforms.facebook, "https://facebook.com/acme"),
            (WorkspaceSocialPlatforms.facebook, "https://fb.com/acme"),
            (WorkspaceSocialPlatforms.youtube, "https://youtube.com/@acme"),
            (WorkspaceSocialPlatforms.youtube, "https://youtu.be/abc"),
            (WorkspaceSocialPlatforms.tiktok, "https://tiktok.com/@acme"),
            (WorkspaceSocialPlatforms.linkedin, "https://linkedin.com/in/acme"),
            (WorkspaceSocialPlatforms.instagram, "https://instagram.com/acme"),
        ],
    )
    def test_accepts_matching_domain(
        self, platform: WorkspaceSocialPlatforms, good_url: str
    ) -> None:
        WorkspaceSocialLink.model_validate(
            {"platform": platform.value, "url": good_url}
        )

    @pytest.mark.parametrize(
        ("platform", "wrong_url"),
        [
            (WorkspaceSocialPlatforms.x, "https://facebook.com/fake"),
            (WorkspaceSocialPlatforms.github, "https://gitlab.com/fake"),
            (WorkspaceSocialPlatforms.linkedin, "https://x.com/fake"),
            (WorkspaceSocialPlatforms.youtube, "https://vimeo.com/fake"),
        ],
    )
    def test_rejects_mismatched_domain(
        self, platform: WorkspaceSocialPlatforms, wrong_url: str
    ) -> None:
        # Cross-brand impersonation defence. A regression letting
        # ``platform=x`` accept a ``facebook.com`` URL would let a
        # workspace claim the wrong social handle on its profile.
        with pytest.raises(ValidationError):
            WorkspaceSocialLink.model_validate(
                {"platform": platform.value, "url": wrong_url}
            )

    def test_other_platform_accepts_any_url(self) -> None:
        # ``other`` is the escape hatch for platforms Rapidly
        # doesn't pin — skips the domain check.
        WorkspaceSocialLink.model_validate(
            {"platform": "other", "url": "https://mastodon.social/@acme"}
        )


# ── Social platforms enum ──


class TestWorkspaceSocialPlatforms:
    def test_covers_known_platforms(self) -> None:
        values = {e.value for e in WorkspaceSocialPlatforms}
        assert values == {
            "x",
            "github",
            "facebook",
            "instagram",
            "youtube",
            "tiktok",
            "linkedin",
            "other",
        }


# ── Legacy status coalescence ──


class TestLegacyWorkspaceStatusCoalescence:
    @pytest.mark.parametrize(
        ("status", "legacy"),
        [
            (WorkspaceStatus.CREATED, LegacyWorkspaceStatus.CREATED),
            (
                WorkspaceStatus.ONBOARDING_STARTED,
                LegacyWorkspaceStatus.ONBOARDING_STARTED,
            ),
            # Both review states collapse to UNDER_REVIEW — the SDK's
            # coarsened view. A regression surfacing INITIAL_REVIEW /
            # ONGOING_REVIEW here would break client apps reading the
            # legacy status field.
            (WorkspaceStatus.INITIAL_REVIEW, LegacyWorkspaceStatus.UNDER_REVIEW),
            (WorkspaceStatus.ONGOING_REVIEW, LegacyWorkspaceStatus.UNDER_REVIEW),
            (WorkspaceStatus.DENIED, LegacyWorkspaceStatus.DENIED),
            (WorkspaceStatus.ACTIVE, LegacyWorkspaceStatus.ACTIVE),
        ],
    )
    def test_from_status(
        self, status: WorkspaceStatus, legacy: LegacyWorkspaceStatus
    ) -> None:
        assert LegacyWorkspaceStatus.from_status(status) is legacy

    def test_legacy_enum_has_exactly_five_values(self) -> None:
        # The five legacy buckets — a silent addition would surface
        # in the SDK without corresponding frontend handling.
        assert {e.value for e in LegacyWorkspaceStatus} == {
            "created",
            "onboarding_started",
            "under_review",
            "denied",
            "active",
        }


# ── WorkspaceCreate defaults ──


class TestWorkspaceCreateDefaults:
    def test_default_presentment_currency_is_usd(self) -> None:
        from rapidly.core.currency import PresentmentCurrency

        body = WorkspaceCreate(name="Acme", slug="acme")
        assert body.default_presentment_currency == PresentmentCurrency.usd
