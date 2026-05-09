"""JSON Web Key (JWKS) generation and loading utilities."""

from __future__ import annotations

import argparse
import pathlib
import sys
from typing import Annotated, Any

from authlib.jose import JsonWebKey, KeySet
from pydantic import PlainValidator

_DEFAULT_KEY_SIZE = 4096

_SETUP_HINT = "Generate a local JWKS file with:  uv run task generate_dev_jwks"


def generate_jwks(kid: str, size: int = _DEFAULT_KEY_SIZE) -> str:
    """Create a new RSA key-pair wrapped in a JWKS JSON string."""
    key = JsonWebKey.generate_key(
        "RSA", size, {"kid": kid, "use": "sig"}, is_private=True
    )
    return KeySet(keys=[key]).as_json(is_private=True)


def _load_jwks(value: Any) -> KeySet:
    filepath = pathlib.Path(str(value))
    if not filepath.is_file():
        raise ValueError(
            f"JWKS path '{value}' does not exist or is not a file.\n{_SETUP_HINT}"
        )

    try:
        raw = filepath.read_text().strip()
        return JsonWebKey.import_key_set(raw)
    except ValueError as exc:
        raise ValueError(f"'{value}' is not a valid JWKS file.\n{_SETUP_HINT}") from exc


JWKSFile = Annotated[KeySet, PlainValidator(_load_jwks)]

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate JWKS")
    parser.add_argument("kid", type=str, help="Key ID")
    parser.add_argument(
        "--size", type=int, default=_DEFAULT_KEY_SIZE, help="RSA key size"
    )
    args = parser.parse_args()
    sys.stdout.write(generate_jwks(args.kid, args.size))
    sys.stdout.write("\n")
