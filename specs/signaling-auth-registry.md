# Spec: Signaling auth validator registry + role normalization

**Phase:** A, PR 3
**Status:** Draft → Implemented in this commit
**Related PRs:** PR 1 (`session_kind`), PR 2 (transport lift)

## Goal

Decouple `signaling.py` from file-sharing-specific auth so future session kinds (Screen, Watch, Call, Collab) can register their own validators without touching the hot-path authentication code.

**No behaviour change.** Every file-sharing auth path — host secret check, guest reader-token check, paid-channel payment-token check — continues to produce identical results and identical error/close codes.

## Non-goals

- No new session kinds land in this PR. Only `("file", "host")` and `("file", "guest")` validators are registered.
- No Redis pub/sub (that's PR 4). Single-worker constraint is unchanged.
- No frontend UI changes. Only the type union on `SignalingClient.connect()` is widened to accept the canonical names.
- No new close codes. Existing 4001/4003/4008/4009/4029 semantics preserved.

## Design

### 1. Role normalization

**Canonical roles on the wire become `host` / `guest`**. The server accepts the old names (`uploader` / `downloader`) as aliases for one release window, then drops them.

```python
# In _authenticate, immediately after reading msg["role"]:
ROLE_ALIASES = {"uploader": "host", "downloader": "guest"}
role = ROLE_ALIASES.get(role, role)
if role not in ("host", "guest"):
    await _send_error(ws, "Invalid role")
    await ws.close(code=4001, reason="Invalid role")
    return None
```

From this point down, every check in `signaling.py` reads against the canonical `host` / `guest` — no compat checks scattered across the file.

Internal field rename: `Room.uploader_id` → `Room.host_id`. The field is private to `SignalingManager`; no external API exposes it.

### 2. Validator registry

```python
@dataclass
class AuthContext:
    ws: WebSocket
    slug: str
    role: str            # canonical "host" or "guest"
    channel: ChannelData
    msg: dict[str, Any]  # the auth message
    repo: ChannelRepository
    client_ip: str

AuthValidator = Callable[[AuthContext], Awaitable[bool]]

_AUTH_VALIDATORS: dict[tuple[str, str], AuthValidator] = {}

def register_auth_validator(
    session_kind: str, role: str
) -> Callable[[AuthValidator], AuthValidator]:
    """Decorator: registers a validator for a (session_kind, role) pair.

    Raises RuntimeError on duplicate registration so we fail loudly at
    import time rather than silently shadowing an existing validator.
    """
```

The validator returns `True` on success and is responsible for sending the appropriate error message + closing the WebSocket on failure (matches the current inline pattern — some errors say "Authentication failed" with close 4003, paid-channel failure says "Payment required"). This preserves existing error-semantics exactly.

### 3. Two registered validators for `session_kind="file"`

Each is a verbatim extraction of the current inline code:

- `_validate_file_host` — HMAC-compare `channel.secret` against `hash_secret(msg["secret"])`.
- `_validate_file_guest` — reader-token validation + pending-token check + payment-token check for paid channels (with cookie fallback `rapidly_pt`, decrypted via `_decrypt_token`).

### 4. `_authenticate` becomes thin

After the rename + registry:

```python
async def _authenticate(ws, slug, redis, *, client_ip="unknown"):
    # read + parse auth message, channel fetch, role normalization ...
    repo = ChannelRepository(redis)
    channel = await repo.fetch_channel(slug)
    if channel is None:
        await _send_error(ws, "Authentication failed")
        await ws.close(code=4003, reason="Forbidden")
        return None

    validator = _AUTH_VALIDATORS.get((channel.session_kind, role))
    if validator is None:
        # Unknown kind-role pair. Fail closed.
        await _send_error(ws, "Authentication failed")
        await ws.close(code=4003, reason="Forbidden")
        return None

    ctx = AuthContext(
        ws=ws, slug=slug, role=role, channel=channel, msg=msg,
        repo=repo, client_ip=client_ip,
    )
    if not await validator(ctx):
        # Validator already sent the specific error and closed the ws.
        return None

    peer_id = str(uuid.uuid4())
    return (Peer(peer_id=peer_id, ws=ws, role=role), channel.short_slug)
```

### 5. Downstream call sites

- Line 535 (`connect-request` routing): `room.uploader_id` → `room.host_id`.
- Line 574 ("only uploader sends metadata"): `peer.role == "uploader"` → `peer.role == "host"`.
- Lines 624, 643–644 (one-host-per-room check): `"uploader"` → `"host"`.
- `signaling_manager.remove_peer` (line 235): `room.uploader_id` → `room.host_id`.

### 6. Frontend

`SignalingClient.connect()` role type widens from `'uploader' | 'downloader'` to `'uploader' | 'downloader' | 'host' | 'guest'`. Existing two call sites continue to pass `'uploader'`/`'downloader'` — no functional change. New chambers in future PRs will pass `'host'`/`'guest'`.

## Data-model edge cases

| Scenario | Behaviour |
|---|---|
| Client sends `role: "uploader"` | Normalized to `"host"`, validator `("file", "host")` runs. Unchanged behaviour. |
| Client sends `role: "host"` | Validator `("file", "host")` runs directly. New path, same outcome. |
| Client sends `role: "admin"` (unknown) | Rejected with "Invalid role", close 4001. |
| Channel has `session_kind` future value we don't know | No validator registered → generic auth failure + close 4003. |
| Stored `session_kind` is literally `"file"` (the 100% case today) | Unchanged behaviour. |

## Tests

1. `register_auth_validator` stores the callable at `(kind, role)`.
2. Re-registering the same `(kind, role)` raises `RuntimeError`.
3. Role aliases: legacy `"uploader"` resolves to `"host"`; `"downloader"` resolves to `"guest"`.
4. Unknown role is rejected by the role-parse step before hitting the registry.
5. Unknown `session_kind` with a valid role returns None (no validator).
6. The two file validators themselves behave identically to pre-refactor code (this is covered by not-breaking existing integration tests and by direct unit tests of each validator against FakeRedis).

## References consulted

- **Polar upstream:** their auth uses per-domain permission decorators (`rapidly/identity/auth/permissions.py` pattern). We re-use the same registry-of-callables idea here, sized for WebSocket auth.
- **Chamber reference:** N/A for this PR.
- **LiveKit:** their auth is JWT-based, not a good reference for our first-message + channel-secret model.

## Risk

Medium — this is the signaling hot path.

**Mitigations:**
- Role aliases keep every current client working across the deploy window (bit-for-bit identical wire behaviour for `'uploader'` / `'downloader'`).
- Validators are literal extractions of the existing inline code — no logic rewrites.
- Every error path (code + message) is preserved.

**Kill criterion:** file-sharing error rate rises >0.1% over baseline in staging after the deploy. Revert.
