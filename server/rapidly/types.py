"""Shared type aliases used across the Rapidly backend.

Lightweight union types for JSON-shaped data that avoid importing
heavier schema libraries at module scope.
"""

from typing import Any

# A JSON object: mapping of string keys to arbitrary values.
JSONDict = dict[str, Any]
