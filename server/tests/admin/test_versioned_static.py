"""Tests for ``rapidly/admin/versioned_static.py``.

Content-hash cache-busting for admin static assets. Three
load-bearing surfaces:

- ``_HASH_TRUNCATION_LENGTH = 8`` — the URL-safe truncation. Drift
  shorter increases collision risk (different files yielding the
  same ``?v=`` and stale cache hits); drift longer wastes URL
  budget.
- ``_FALLBACK_VERSION = "1"`` — the version returned when the
  file cannot be read (missing dir, I/O error, non-existent
  path). Drift to None / empty string would emit ``?v=`` and
  some CDNs treat the empty query as a cache key, defeating
  cache busting on subsequent legit reads.
- ``get_file_version`` returns SHA-256-first-8-hex-chars of the
  file content. Drift to MD5 / different truncation would change
  the version on every redeploy of the admin and bust the cache
  even when the file content didn't change.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from rapidly.admin.versioned_static import (
    _FALLBACK_VERSION,
    _HASH_TRUNCATION_LENGTH,
    VersionedStaticFiles,
)


class TestConstants:
    def test_hash_truncation_pinned_to_8(self) -> None:
        # Pin: 8 hex chars (32 bits of collision resistance).
        # Drift shorter risks ``?v=`` collisions (stale cache
        # served for two files with same prefix).
        assert _HASH_TRUNCATION_LENGTH == 8

    def test_fallback_version_pinned(self) -> None:
        # Pin: the "1" fallback. Drift to "" would emit ``?v=``
        # which some CDNs treat as a unique cache key; drift to
        # None would crash the URL builder on f-string format.
        assert _FALLBACK_VERSION == "1"


class TestGetFileVersion:
    def test_hashes_file_content(self, tmp_path: Path) -> None:
        # Pin: SHA-256 first 8 hex chars of the file content.
        # Drift to MD5 / different length would change the
        # version on every redeploy and re-bust the cache.
        f = tmp_path / "app.css"
        f.write_bytes(b"body { color: red; }")
        expected = hashlib.sha256(b"body { color: red; }").hexdigest()[:8]

        static = VersionedStaticFiles(directory=str(tmp_path))
        assert static.get_file_version("app.css") == expected

    def test_same_content_same_version(self, tmp_path: Path) -> None:
        # Pin: deterministic. Same content always yields the same
        # version (pin against a regression that introduced randomness
        # / timestamp-based hashing).
        a = tmp_path / "a.css"
        a.write_bytes(b"x")
        static = VersionedStaticFiles(directory=str(tmp_path))
        v1 = static.get_file_version("a.css")
        # Clear lru_cache so we re-read.
        static.get_file_version.cache_clear()
        v2 = static.get_file_version("a.css")
        assert v1 == v2

    def test_different_content_different_version(self, tmp_path: Path) -> None:
        a = tmp_path / "a.css"
        a.write_bytes(b"x")
        b = tmp_path / "b.css"
        b.write_bytes(b"y")
        static = VersionedStaticFiles(directory=str(tmp_path))
        assert static.get_file_version("a.css") != static.get_file_version("b.css")

    def test_missing_file_returns_fallback(self, tmp_path: Path) -> None:
        # Pin: a non-existent file returns ``"1"`` rather than
        # raising. Otherwise the admin's first request after a
        # bad deploy would 500.
        static = VersionedStaticFiles(directory=str(tmp_path))
        assert static.get_file_version("missing.css") == _FALLBACK_VERSION

    def test_no_directory_returns_fallback(self) -> None:
        # Defensive: when ``directory`` is None (rare init path),
        # the fallback version is returned.
        static = VersionedStaticFiles(directory=None, packages=[("rapidly", "")])
        assert static.get_file_version("app.css") == _FALLBACK_VERSION

    def test_oserror_returns_fallback(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        # Pin: I/O errors during read fall back to ``"1"`` (no
        # crash). E.g., a transient EBUSY on a network mount.
        f = tmp_path / "app.css"
        f.write_bytes(b"x")

        # Monkey-patch read_bytes on Path to raise OSError.
        def boom(self: Path) -> bytes:
            raise OSError("transient")

        monkeypatch.setattr(Path, "read_bytes", boom)

        static = VersionedStaticFiles(directory=str(tmp_path))
        assert static.get_file_version("app.css") == _FALLBACK_VERSION

    def test_returns_8_hex_chars(self, tmp_path: Path) -> None:
        # Pin: the result is exactly 8 lowercase hex characters.
        f = tmp_path / "x.css"
        f.write_bytes(b"content")
        static = VersionedStaticFiles(directory=str(tmp_path))
        v = static.get_file_version("x.css")
        assert len(v) == 8
        # All hex characters.
        int(v, 16)


class TestLruCache:
    def test_repeated_calls_use_cache(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Pin: ``lru_cache`` caches the result so the file is only
        # read ONCE per process lifetime per path. Drift to no-cache
        # would re-hash on every template render (perf regression).
        f = tmp_path / "app.css"
        f.write_bytes(b"x")
        read_count = {"n": 0}

        original_read_bytes = Path.read_bytes

        def counted_read(self: Path) -> bytes:
            read_count["n"] += 1
            return original_read_bytes(self)

        monkeypatch.setattr(Path, "read_bytes", counted_read)

        static = VersionedStaticFiles(directory=str(tmp_path))
        v1 = static.get_file_version("app.css")
        v2 = static.get_file_version("app.css")
        v3 = static.get_file_version("app.css")
        assert v1 == v2 == v3
        # File read EXACTLY once despite 3 calls.
        assert read_count["n"] == 1
