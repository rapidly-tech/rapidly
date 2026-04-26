# Spec: `session_kind` field on `ChannelData`

**Phase:** A, PR 1
**Status:** Draft → Implemented in this commit
**Related PRs:** PR 0 (verify.sh)

## Goal

Widen `ChannelData` to describe *what kind of session* a channel is, without breaking any existing Redis entries and without changing any runtime behaviour.

## Non-goals

- No new session kinds land in this PR. The only registered kind remains `"file"`.
- No API endpoints change.
- No migrations. Existing Redis entries continue to read back correctly.
- No dispatch logic added — that's PR 3 (auth validator registry).

## Design

### 1. New constant

```python
SESSION_KINDS: set[str] = {"file"}
```

Single source of truth for the set of supported session kinds. Future PRs (Screen, Watch, etc.) extend this set.

### 2. Validator helper

```python
def validate_session_kind(kind: str) -> None:
    """Raise ValueError if kind is not in SESSION_KINDS."""
```

Centralised so that any caller constructing a `ChannelData` by a kind-string (e.g. from a future API body) has one place to enforce the invariant.

### 3. `ChannelData` field

```python
@dataclass
class ChannelData:
    ...
    session_kind: str = "file"
```

- Default `"file"` means no existing caller needs to change.
- `dataclasses.asdict` serialises the new field automatically.

### 4. `ChannelData.from_dict` backward compatibility

```python
session_kind=data.get("session_kind", "file")
```

Existing Redis entries were written before this field existed, so `data` won't contain the key. The `.get(..., "file")` default ensures they read back as file sessions — **no migration required**.

## Data-model edge cases

| Scenario | Behaviour |
|---|---|
| Old Redis entry (no `session_kind`) | Reads as `session_kind="file"`. |
| New channel created without specifying kind | Defaults to `"file"` (backward compat with every existing `create_channel` caller). |
| `from_dict` called with an unknown kind | Returns a `ChannelData` with that kind; **no validation at this layer** (deliberate — `from_dict` must always succeed on any Redis payload we wrote; validation happens at construction sites via `validate_session_kind`). |

## What is *not* being enforced yet

- Per-kind required fields. Today a `session_kind="file"` channel could technically be stored without `file_name` — that's already true before this change. Adding the guard would break current behaviour and is out of scope.
- Per-kind auth dispatch. File-sharing still uses the hardcoded paths in `_authenticate`; the validator registry lands in PR 3.

## Tests

1. `ChannelData` default has `session_kind="file"`.
2. `to_dict()` → `from_dict()` round-trip preserves `session_kind`.
3. Old-format dict (no `session_kind` key) → `from_dict` returns `"file"`.
4. `SESSION_KINDS` contains `"file"`.
5. `validate_session_kind("file")` → no raise.
6. `validate_session_kind("bogus")` → `ValueError`.

## References consulted

- Polar upstream: no direct prior art — Polar's models use SQLAlchemy, not Redis dataclasses. Pattern borrowed from Rapidly's own `SecretData` which already uses the same dataclass + `from_dict`/`to_dict` pattern.
- Chamber reference: N/A for this PR (schema widening, not a feature).

## Risk

Very low — pure type widening with a default that matches every existing write.
