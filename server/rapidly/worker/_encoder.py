"""Dramatiq message encoder that strips ephemeral options before serialisation."""

import json
import uuid
from typing import Any

import dramatiq


def _default_serializer(obj: Any) -> Any:
    if isinstance(obj, uuid.UUID):
        return str(obj)
    raise TypeError(f"Cannot serialise {type(obj).__name__}")


class JSONEncoder(dramatiq.JSONEncoder):
    """Strips middleware-injected ephemeral keys so messages stay small in Redis."""

    def __init__(self, broker: dramatiq.Broker | None = None) -> None:
        self._ephemeral_keys: frozenset[str] = frozenset()
        if broker is not None:
            keys: set[str] = set()
            for mw in broker.middleware:
                keys |= getattr(mw, "ephemeral_options", set())
            self._ephemeral_keys = frozenset(keys)

    def encode(self, data: dict[str, Any]) -> bytes:
        if (options := data.get("options")) and self._ephemeral_keys:
            data = {
                **data,
                "options": {
                    k: v for k, v in options.items() if k not in self._ephemeral_keys
                },
            }
        return json.dumps(
            data, separators=(",", ":"), default=_default_serializer
        ).encode("utf-8")
