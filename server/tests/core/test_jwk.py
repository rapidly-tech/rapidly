"""Tests for ``rapidly/core/jwk.py`` — JWKS generation + the
``JWKSFile`` Pydantic-annotated loader.

RSA key generation is expensive — tests pass ``size=2048`` to keep the
suite fast; the production default (4096) is enforced elsewhere.
The properties we care about (JSON shape, round-trip, file-not-found
behaviour) are size-independent.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from authlib.jose import KeySet
from pydantic import BaseModel, ValidationError

from rapidly.core.jwk import JWKSFile, generate_jwks


class TestGenerateJwks:
    def test_returns_a_valid_json_string(self) -> None:
        raw = generate_jwks("test-kid", size=2048)
        data = json.loads(raw)
        assert "keys" in data
        assert isinstance(data["keys"], list)
        assert len(data["keys"]) == 1

    def test_sets_the_kid_claim(self) -> None:
        raw = generate_jwks("my-kid-123", size=2048)
        data = json.loads(raw)
        assert data["keys"][0]["kid"] == "my-kid-123"

    def test_marks_key_for_signing_use(self) -> None:
        raw = generate_jwks("k", size=2048)
        data = json.loads(raw)
        assert data["keys"][0]["use"] == "sig"

    def test_is_rsa(self) -> None:
        raw = generate_jwks("k", size=2048)
        data = json.loads(raw)
        assert data["keys"][0]["kty"] == "RSA"

    def test_private_key_material_present(self) -> None:
        # as_json(is_private=True) serialises the full key-pair. Public
        # components: n, e. Private: d (+ p, q, dp, dq, qi).
        raw = generate_jwks("k", size=2048)
        data = json.loads(raw)
        key = data["keys"][0]
        # Public material.
        assert "n" in key
        assert "e" in key
        # Private material present (so the server can SIGN, not just
        # verify).
        assert "d" in key

    def test_different_kids_produce_distinct_key_sets(self) -> None:
        # Each call generates fresh entropy. Two keys with different kids
        # should have different ``n`` moduli.
        a = json.loads(generate_jwks("a", size=2048))
        b = json.loads(generate_jwks("b", size=2048))
        assert a["keys"][0]["n"] != b["keys"][0]["n"]


class TestJwksFileLoader:
    """``JWKSFile`` is an ``Annotated[KeySet, PlainValidator(_load_jwks)]``.
    The validator reads a file path, parses JWKS JSON, and returns a
    ``KeySet`` — caller failures raise ``ValidationError`` via Pydantic.
    """

    class _Model(BaseModel):
        jwks: JWKSFile

    def test_loads_a_valid_jwks_file(self, tmp_path: Path) -> None:
        raw = generate_jwks("k", size=2048)
        path = tmp_path / "jwks.json"
        path.write_text(raw)

        model = self._Model(jwks=str(path))
        assert isinstance(model.jwks, KeySet)

    def test_rejects_nonexistent_path(self, tmp_path: Path) -> None:
        missing = tmp_path / "does-not-exist.json"
        with pytest.raises(ValidationError) as excinfo:
            self._Model(jwks=str(missing))
        # The setup-hint string must land in the validation error so the
        # operator sees how to generate the file.
        assert "generate_dev_jwks" in str(excinfo.value)

    def test_rejects_malformed_jwks_content(self, tmp_path: Path) -> None:
        path = tmp_path / "bad.json"
        path.write_text("{this is not valid jwks}")
        with pytest.raises(ValidationError) as excinfo:
            self._Model(jwks=str(path))
        # The malformed-path branch also surfaces the setup hint.
        assert "not a valid JWKS file" in str(
            excinfo.value
        ) or "generate_dev_jwks" in str(excinfo.value)

    def test_rejects_when_path_points_to_a_directory(self, tmp_path: Path) -> None:
        # ``filepath.is_file()`` returns False for directories, so the
        # validator must reject with the same setup-hint error.
        with pytest.raises(ValidationError):
            self._Model(jwks=str(tmp_path))
