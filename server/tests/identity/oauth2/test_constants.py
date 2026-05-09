"""Tests for ``rapidly/identity/oauth2/constants.py``.

Pins the OAuth2 token-prefix scheme. Each prefix is the identifying
string every downstream validator keys on — if a refactor accidentally
changes ``rapidly_ci_`` to ``rapidly_client_`` for example, every
existing client-id in the database becomes unrecognisable.

Also pins the per-SubType (user / workspace) prefix split — the
discriminator between a user-owned token and a workspace-owned token
travels in this single-letter segment, so silently collapsing or
swapping them would be a cross-subject token-reuse vulnerability.
"""

from __future__ import annotations

from rapidly.identity.oauth2.constants import (
    ACCESS_TOKEN_PREFIX,
    AUTHORIZATION_CODE_PREFIX,
    CLAIMS_SUPPORTED,
    CLIENT_ID_PREFIX,
    CLIENT_REGISTRATION_TOKEN_PREFIX,
    CLIENT_SECRET_PREFIX,
    ID_TOKEN_SIGNING_ALG_VALUES_SUPPORTED,
    ISSUER,
    REFRESH_TOKEN_PREFIX,
    SERVICE_DOCUMENTATION,
    SUBJECT_TYPES_SUPPORTED,
    WEBHOOK_SECRET_PREFIX,
    is_registration_token_prefix,
)
from rapidly.identity.oauth2.sub_type import SubType


class TestTokenPrefixes:
    def test_prefixes_share_the_rapidly_namespace(self) -> None:
        # Every Rapidly-issued token starts with ``rapidly_`` so
        # operators can grep logs and spot tokens quickly.
        for p in (
            CLIENT_ID_PREFIX,
            CLIENT_SECRET_PREFIX,
            CLIENT_REGISTRATION_TOKEN_PREFIX,
            AUTHORIZATION_CODE_PREFIX,
            WEBHOOK_SECRET_PREFIX,
        ):
            assert p.startswith("rapidly_"), p

    def test_prefixes_are_distinct(self) -> None:
        # If two token types shared a prefix, callers couldn't tell
        # them apart at the bearer layer. Pinning uniqueness.
        prefixes = {
            CLIENT_ID_PREFIX,
            CLIENT_SECRET_PREFIX,
            CLIENT_REGISTRATION_TOKEN_PREFIX,
            AUTHORIZATION_CODE_PREFIX,
            WEBHOOK_SECRET_PREFIX,
            ACCESS_TOKEN_PREFIX[SubType.user],
            ACCESS_TOKEN_PREFIX[SubType.workspace],
            REFRESH_TOKEN_PREFIX[SubType.user],
            REFRESH_TOKEN_PREFIX[SubType.workspace],
        }
        assert len(prefixes) == 9

    def test_exact_prefix_values(self) -> None:
        # Changing any of these is a breaking change — every existing
        # token in the DB becomes unrecognisable. Pinning values so a
        # silent rename fails loudly in CI.
        assert CLIENT_ID_PREFIX == "rapidly_ci_"
        assert CLIENT_SECRET_PREFIX == "rapidly_cs_"
        assert CLIENT_REGISTRATION_TOKEN_PREFIX == "rapidly_crt_"
        assert AUTHORIZATION_CODE_PREFIX == "rapidly_ac_"
        assert WEBHOOK_SECRET_PREFIX == "rapidly_whs_"


class TestAccessAndRefreshTokenPrefixes:
    def test_user_vs_workspace_access_prefixes_differ(self) -> None:
        # The u / o discriminator is what distinguishes a user access
        # token from a workspace access token. If they collapsed, a
        # workspace-scoped token could be accepted on a user-scoped
        # endpoint — a cross-subject auth bypass.
        assert (
            ACCESS_TOKEN_PREFIX[SubType.user] != ACCESS_TOKEN_PREFIX[SubType.workspace]
        )

    def test_user_vs_workspace_refresh_prefixes_differ(self) -> None:
        assert (
            REFRESH_TOKEN_PREFIX[SubType.user]
            != REFRESH_TOKEN_PREFIX[SubType.workspace]
        )

    def test_access_and_refresh_prefixes_differ(self) -> None:
        # Access tokens must be distinguishable from refresh tokens
        # even for the same subject type — otherwise a refresh token
        # could be submitted as a bearer token.
        for sub_type in SubType:
            assert ACCESS_TOKEN_PREFIX[sub_type] != REFRESH_TOKEN_PREFIX[sub_type]

    def test_covers_every_SubType(self) -> None:
        # Drift-catch: adding a SubType member without updating the
        # prefix dicts would crash at runtime.
        assert set(ACCESS_TOKEN_PREFIX.keys()) == set(SubType)
        assert set(REFRESH_TOKEN_PREFIX.keys()) == set(SubType)


class TestIsRegistrationTokenPrefix:
    def test_true_for_crt_prefixed_values(self) -> None:
        assert is_registration_token_prefix("rapidly_crt_abc123") is True

    def test_false_for_client_id_prefix(self) -> None:
        # Near-miss — CI vs CRT would be easy to confuse if the check
        # used a weaker contains() instead of startswith.
        assert is_registration_token_prefix("rapidly_ci_abc") is False

    def test_false_for_other_rapidly_prefixes(self) -> None:
        assert is_registration_token_prefix("rapidly_cs_x") is False
        assert is_registration_token_prefix("rapidly_at_u_x") is False

    def test_false_for_non_rapidly_inputs(self) -> None:
        assert is_registration_token_prefix("some-other-token") is False
        assert is_registration_token_prefix("") is False


class TestOidcServerConfig:
    def test_issuer_is_the_canonical_rapidly_tech_url(self) -> None:
        # Pinned explicitly — the issuer is the string the server
        # advertises in ``iss`` claims, and clients validate against
        # their configured issuer. A silent change would break every
        # integrated client's validation.
        assert ISSUER == "https://rapidly.tech"

    def test_service_documentation_points_at_docs_rapidly_tech(self) -> None:
        assert SERVICE_DOCUMENTATION == "https://rapidly.tech/docs"

    def test_only_public_subject_types_supported(self) -> None:
        # Pairwise subject type is an OIDC privacy feature we haven't
        # enabled. Pinned so a silent flip to ``["public", "pairwise"]``
        # is caught.
        assert SUBJECT_TYPES_SUPPORTED == ["public"]

    def test_id_token_signing_uses_rs256_only(self) -> None:
        # RS256 is the only documented algorithm. If a refactor added
        # HS256 or ``none``, existing client-side libraries would reject
        # tokens signed with those — pinning ensures the discovery
        # document stays truthful.
        assert ID_TOKEN_SIGNING_ALG_VALUES_SUPPORTED == ["RS256"]

    def test_claims_supported_contains_oidc_standard_set(self) -> None:
        # ``sub``, ``name``, ``email``, ``email_verified`` — the
        # minimal OIDC profile claim set.
        assert set(CLAIMS_SUPPORTED) >= {
            "sub",
            "name",
            "email",
            "email_verified",
        }
