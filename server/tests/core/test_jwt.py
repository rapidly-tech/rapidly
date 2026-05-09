"""Tests for ``rapidly/core/jwt.py`` — signed-token encode/decode with
a mandatory ``type`` claim that maps to the JWT ``aud`` field.

The ``type``→``aud`` mapping is the whole reason this module exists:
it prevents a token minted for one purpose (e.g. ``discord_oauth``) from
being replayed in a context expecting another (e.g. ``customer_oauth``).
Every invariant that protects that property is pinned here.
"""

from __future__ import annotations

import jwt as _jwt
import pytest
from jwt import (
    InvalidAudienceError,
    InvalidSignatureError,
    InvalidTokenError,
)

from rapidly.core.jwt import DecodeError, ExpiredSignatureError, decode, encode


class TestEncodeDecodeRoundTrip:
    def test_decode_returns_the_original_payload_fields(self) -> None:
        token = encode(
            data={"user_id": "u-123", "foo": "bar"},
            secret="a-32-byte-test-secret-abcdefghij",
            type="discord_oauth",
        )
        payload = decode(
            token=token, secret="a-32-byte-test-secret-abcdefghij", type="discord_oauth"
        )
        # Original claims present.
        assert payload["user_id"] == "u-123"
        assert payload["foo"] == "bar"

    def test_encoded_token_carries_the_type_in_the_aud_claim(self) -> None:
        # The type arg MUST land in the ``aud`` claim — that's what the
        # decoder verifies. Pinning via the raw library decode so a
        # refactor that changes which field carries the type is caught.
        token = encode(
            data={"x": 1}, secret="a-32-byte-test-secret-abcdefghij", type="my-purpose"
        )
        raw = _jwt.decode(
            token,
            "a-32-byte-test-secret-abcdefghij",
            algorithms=["HS256"],
            audience="my-purpose",
        )
        assert raw["aud"] == "my-purpose"

    def test_returned_token_is_compact_three_part_jws(self) -> None:
        # JWT compact form: header.payload.signature
        token = encode(data={}, secret="a-32-byte-test-secret-abcdefghij", type="t")
        assert token.count(".") == 2


class TestTypeMismatch:
    def test_decode_rejects_a_token_with_the_wrong_audience(self) -> None:
        # Security critical: a token minted for one purpose MUST NOT
        # decode under a different type. Prevents OAuth-token replay
        # across flows.
        token = encode(
            data={"x": 1}, secret="a-32-byte-test-secret-abcdefghij", type="flow-a"
        )
        with pytest.raises(InvalidAudienceError):
            decode(
                token=token, secret="a-32-byte-test-secret-abcdefghij", type="flow-b"
            )

    def test_decode_accepts_the_matching_audience(self) -> None:
        # Contract check: matching audience decodes cleanly.
        token = encode(
            data={"x": 1}, secret="a-32-byte-test-secret-abcdefghij", type="flow-a"
        )
        payload = decode(
            token=token, secret="a-32-byte-test-secret-abcdefghij", type="flow-a"
        )
        assert payload["aud"] == "flow-a"


class TestSecretMismatch:
    def test_decode_raises_on_wrong_secret(self) -> None:
        token = encode(
            data={"x": 1},
            secret="correct-secret-32-bytes-abcdefghij",
            type="t",
        )
        with pytest.raises(InvalidSignatureError):
            decode(
                token=token,
                secret="wrong-secret-32-bytes-abcdefghijkl",
                type="t",
            )


class TestAlgorithmPin:
    def test_uses_hs256_not_none(self) -> None:
        # ``alg: none`` would accept unsigned tokens — a classic JWT
        # auth-bypass. Pin that encode produces HS256.
        token = encode(data={}, secret="a-32-byte-test-secret-abcdefghij", type="t")
        header = _jwt.get_unverified_header(token)
        assert header["alg"] == "HS256"

    def test_decode_rejects_a_none_algorithm_token(self) -> None:
        # A crafted ``alg: none`` token must fail the HS256 decode path.
        crafted = _jwt.encode(
            {"aud": "t", "x": 1},
            "",  # no key for alg=none
            algorithm="none",
        )
        with pytest.raises(InvalidTokenError):
            decode(token=crafted, secret="a-32-byte-test-secret-abcdefghij", type="t")


class TestExpiredToken:
    def test_expired_token_raises_ExpiredSignatureError(self) -> None:
        # The module re-exports ExpiredSignatureError for callers to
        # catch. The encoder doesn't set ``exp`` itself (caller provides
        # it via data), so we encode an already-expired token manually.
        token = encode(
            data={"x": 1, "exp": 0},  # Unix epoch = ancient past
            secret="a-32-byte-test-secret-abcdefghij",
            type="t",
        )
        with pytest.raises(ExpiredSignatureError):
            decode(token=token, secret="a-32-byte-test-secret-abcdefghij", type="t")


class TestMalformedToken:
    def test_decode_raises_DecodeError_on_garbage(self) -> None:
        with pytest.raises(DecodeError):
            decode(
                token="not-a-jwt", secret="a-32-byte-test-secret-abcdefghij", type="t"
            )

    def test_decode_raises_on_truncated_token(self) -> None:
        with pytest.raises(InvalidTokenError):
            decode(
                token="header.payload",
                secret="a-32-byte-test-secret-abcdefghij",
                type="t",
            )


class TestReExports:
    def test_exports_DecodeError_and_ExpiredSignatureError(self) -> None:
        # Callers (identity, OAuth) import these symbols from this
        # module rather than PyJWT directly. Pinning prevents a
        # refactor that drops the re-export.
        assert DecodeError is _jwt.DecodeError
        assert ExpiredSignatureError is _jwt.ExpiredSignatureError
