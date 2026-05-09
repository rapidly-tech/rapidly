"""Tests for ``rapidly/platform/user/types.py``.

The user types module carries a handful of pinnable contracts:

- ``UserSignupAttribution`` is the marketing-attribution payload
  captured at signup. Every field is optional so a bare ``{}`` must
  validate — a regression making any field required would break the
  signup page when a user arrives without UTM parameters.
- ``UserSignupAttribution.intent`` is a ``Literal["creator"]`` — a
  silent rename of the literal would break the signup-intent-based
  onboarding flow without a type error visible at the API boundary.
- ``UserSignupAttributionQuery`` parses the JSON-encoded attribution
  query param via ``_parse_attribution_query`` — pinning the ``None``
  / empty-string fallback path prevents a 500 on every signup that
  doesn't carry the param.
- ``UserDeletionBlockedReason`` StrEnum exposes
  ``HAS_ACTIVE_WORKSPACES``; the frontend maps this enum to the
  "you can't delete yet" UI copy.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from rapidly.platform.user.types import (
    UserDeletionBlockedReason,
    UserDeletionResponse,
    UserSignupAttribution,
    _parse_attribution_query,
)


class TestUserSignupAttributionIsFullyOptional:
    def test_empty_body_validates(self) -> None:
        # Bare {} is the canonical "no attribution" payload —
        # signups without UTM parameters (direct traffic) must
        # not 422.
        attr = UserSignupAttribution.model_validate({})
        assert attr.intent is None
        assert attr.from_storefront is None
        assert attr.path is None
        assert attr.host is None
        assert attr.utm_source is None
        assert attr.utm_medium is None
        assert attr.utm_campaign is None
        assert attr.campaign is None

    def test_intent_literal_accepts_creator(self) -> None:
        attr = UserSignupAttribution(intent="creator")
        assert attr.intent == "creator"

    def test_intent_rejects_unknown_literal(self) -> None:
        # Pin the literal — a silent addition (``intent="reseller"``)
        # without wiring the onboarding flow would accept payloads
        # the app can't actually handle.
        with pytest.raises(ValidationError):
            UserSignupAttribution.model_validate({"intent": "reseller"})


class TestParseAttributionQuery:
    @pytest.mark.asyncio
    async def test_none_input_returns_none(self) -> None:
        # Direct-traffic signup — query param absent. A regression
        # raising on None would 500 every signup.
        assert await _parse_attribution_query(None) is None

    @pytest.mark.asyncio
    async def test_empty_string_returns_none(self) -> None:
        # ``?attribution=`` resolves to empty string; must behave
        # like the absent case, not blow up on ``model_validate_json("")``.
        assert await _parse_attribution_query("") is None

    @pytest.mark.asyncio
    async def test_valid_json_parses(self) -> None:
        attr = await _parse_attribution_query('{"utm_source":"twitter"}')
        assert attr is not None
        assert attr.utm_source == "twitter"

    @pytest.mark.asyncio
    async def test_malformed_json_raises(self) -> None:
        # Malformed attribution is a client bug — surfacing as a
        # validation error is the documented behaviour. (FastAPI
        # converts this to 422 at the boundary.)
        with pytest.raises(ValidationError):
            await _parse_attribution_query("not-json")


class TestUserDeletionEnum:
    def test_has_active_workspaces_value(self) -> None:
        # Wire value matches the frontend's dictionary key for the
        # "you can't delete yet" copy — renaming breaks the copy
        # lookup silently.
        assert UserDeletionBlockedReason.HAS_ACTIVE_WORKSPACES.value == (
            "has_active_workspaces"
        )

    def test_enum_has_exactly_one_member(self) -> None:
        # Adding a second reason without updating the frontend's
        # copy dictionary would surface as a missing-key UI bug.
        # Pinning forces an intentional update on both sides.
        assert len(list(UserDeletionBlockedReason)) == 1


class TestUserDeletionResponseDefaults:
    def test_empty_list_defaults(self) -> None:
        # Defensive defaults: a deletion that blocks on nothing
        # (the successful-deletion path) must still validate with
        # empty lists, not require callers to pass them.
        resp = UserDeletionResponse(deleted=True)
        assert resp.blocked_reasons == []
        assert resp.blocking_workspaces == []
