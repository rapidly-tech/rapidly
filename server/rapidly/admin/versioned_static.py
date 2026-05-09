"""Content-hash-versioned static file serving for cache-busting.

Extends Starlette's ``StaticFiles`` so that templates can append a
``?v=<hash>`` query parameter derived from each asset's SHA-256 digest.
The result is cached in-process via ``lru_cache`` so the hash is only
computed once per file per process lifetime.
"""

from __future__ import annotations

import hashlib
from functools import lru_cache
from pathlib import Path

from starlette.staticfiles import StaticFiles

_HASH_TRUNCATION_LENGTH: int = 8
_FALLBACK_VERSION: str = "1"


class VersionedStaticFiles(StaticFiles):
    """StaticFiles subclass that exposes a content-hash version per file.

    Used by the admin panel's Jinja2 templates to produce cache-safe URLs.
    """

    @lru_cache(maxsize=64)
    def get_file_version(self, file_path: str) -> str:
        """Return a short hex digest derived from the file's content.

        Falls back to ``"1"`` when the file cannot be read (e.g. missing
        directory, I/O error, or non-existent path).
        """
        try:
            if self.directory is None:
                return _FALLBACK_VERSION

            resolved = Path(self.directory) / file_path
            if not resolved.exists():
                return _FALLBACK_VERSION

            digest = hashlib.sha256(resolved.read_bytes()).hexdigest()
            return digest[:_HASH_TRUNCATION_LENGTH]

        except (OSError, ValueError):
            return _FALLBACK_VERSION
