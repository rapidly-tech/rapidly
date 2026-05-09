# Spec: Screen chamber — server-side session API (PR 5)

**Phase:** B, PR 5 (first Phase B PR; unblocks PR 6 + PR 7)
**Status:** Draft → Implemented in this commit
**Related:** Phase A (merged PRs 0–4b), PR 4c (Redis signaling, #43 open)

## Goal

Add everything the Screen chamber needs on the backend: session creation + invite-token minting + a GET for the public landing, plus the two signaling validators registered for `session_kind="screen"`. This PR does NOT ship any UI or any client-side WebRTC changes — those are PR 6 (media tracks) and PR 7 (UI + revolver landing).

**File sharing is untouched.** Every existing endpoint, auth path, and Redis key is preserved.

## Non-goals

- No frontend code.
- No `PeerDataConnection` extension for media tracks (that's PR 6).
- No revolver landing page (that's PR 7).
- No rate-limit counter generalization (PR 4d if ever needed).
- No payments / paid screen sessions (defer until Screen v1 ships and has usage).

## Design

### 1. Schema additions on `ChannelData`

```python
max_viewers: int = 0              # 0 = unlimited; API caps at 10 for v1
screen_started_at: str | None = None  # ISO-8601 for observability only
```

Both optional. `session_kind="screen"` channels set them; `session_kind="file"` channels don't and their behaviour is unchanged. `from_dict` handles missing keys as defaults (same backward-compat pattern we've been using).

Extend `SESSION_KINDS` to `{"file", "screen"}` via `validate_session_kind`.

### 2. New module — `server/rapidly/sharing/screen/`

Matches the standard Rapidly per-module convention:

| File | Role |
|---|---|
| `api.py` | HTTP handlers: `POST /session`, `GET /session/{slug}`, `POST /session/{slug}/invite`, `DELETE /session/{slug}`. |
| `actions.py` | Business logic — `create_screen_session`, `mint_invite_token`, `close_screen_session`. |
| `queries.py` | Redis layer for invite tokens. Wraps `ChannelRepository` from `file_sharing/queries.py` for channel-backed state. |
| `types.py` | Pydantic request/response models. |
| `permissions.py` | Auth dependency declarations (reuses workspace auth if authenticated; allows anonymous host for v1 parity with file-sharing). |

Mounted under `/api/v1/screen/` in the global router.

### 3. Invite-token model

Hosts create sessions; each guest must present a one-time invite token to connect. Token mint endpoint requires the channel secret so only the host can issue them.

**Redis layout:**
- `file-sharing:screen:invite:{slug}` — SET of SHA-256 hashes of issued invite tokens. TTL = channel TTL.
- Token consumed on successful signaling auth? **No** for v1 — guests can disconnect/reconnect with the same invite during the session. One guest per invite is enforced by the `max_viewers` cap, not by one-time-use tokens.

### 4. Signaling validators for `session_kind="screen"`

Two registered via `@register_auth_validator`:

- `("screen", "host")` — HMAC-compares `channel.secret` against `_hash_secret(msg["secret"])`. Identical pattern to `_validate_file_host`.
- `("screen", "guest")` — looks up the token hash in the invite SET. `SISMEMBER` returns True → accept; False → reject with `Authentication failed` + close 4003.

Both registered at module import time by importing `screen.signaling_validators` from the signaling module.

### 5. API endpoints

| Method | Path | Body | Returns | Auth |
|---|---|---|---|---|
| `POST` | `/api/v1/screen/session` | `{title?, max_viewers?: int (≤10)}` | `{short_slug, long_slug, secret, invite_template, expires_at}` | anonymous OK (matches file-sharing) |
| `POST` | `/api/v1/screen/session/{slug}/invite` | `{secret}` | `{invite_token}` | proven by secret |
| `GET` | `/api/v1/screen/session/{slug}` | — | `{title, max_viewers, started_at, host_connected: bool}` | anonymous (public info only; no secrets) |
| `DELETE` | `/api/v1/screen/session/{slug}` | `{secret}` | 204 | proven by secret |

`invite_template` is a client-side string like `"/screen/{slug}?t={invite_token}"` that the host renders and shares out-of-band. Each invite mint returns a *separate* token so the host can revoke per-guest if we ever add that later.

### 6. Feature flag

New setting: `FILE_SHARING_SCREEN_ENABLED: bool = False`.

When `False`, the router excludes the screen endpoints and the signaling validators are still registered (safe — no channels will have `session_kind="screen"` without the API path). When `True`, endpoints become available.

Flip path: config flag → staging → prod → public.

### 7. Rate limits

Reuse the existing `file-sharing:ws-rate:conn:{ip_hash}` WebSocket connection rate limit — shared across file-sharing and screen, which matches the policy that "one IP shouldn't spawn unlimited P2P sessions regardless of chamber."

API endpoints rely on the existing workspace-scoped API rate limiting; for anonymous callers the per-IP HTTP rate limiter applies.

## Data-model implications

- Redis keys: one new prefix `file-sharing:screen:invite:` (the SET). All other channel-related Redis keys are reused unchanged.
- `ChannelData.session_kind` gains one more legal value.
- Wire protocol unchanged at the signaling layer — hosts send `{role: "host", secret}`, guests send `{role: "guest", token}`. The "secret" still unlocks host for any chamber; the "token" means different things per chamber (reader token for file, invite token for screen), but the auth validator registry handles that dispatch transparently.

## Tests

1. `SESSION_KINDS` includes `"screen"`; `validate_session_kind("screen")` does not raise.
2. `ChannelData` round-trips `session_kind="screen"` + `max_viewers` + `screen_started_at`.
3. `create_screen_session` creates a channel with `session_kind="screen"` and the right defaults.
4. `mint_invite_token` requires the secret; wrong secret returns None.
5. Invite validator accepts a minted token; rejects an unknown one with proper close code.
6. Host validator with wrong secret returns False + sends the generic auth-failed error.
7. API endpoints hit the right status codes: 200 for POST session, 200 for GET, 200 for mint invite, 204 for DELETE.
8. `max_viewers > 10` is rejected at the request-schema level.

## References consulted

- **Polar upstream:** no direct equivalent. We follow the existing `sharing/file_sharing/` module layout closely.
- **Chamber reference:** Screen-share-only codebases (`screego`) are too different architecturally to copy from — the key insight (one host's `addTrack()` + N guests' `ontrack`) is browser-native and lands in PR 6.

## Risk

Low for this PR:
- Default flag value is `False` so the endpoints don't appear in the API surface unless explicitly enabled.
- Auth validators are additive; the existing file-sharing ones are untouched.
- No Redis migrations — the new invite-token SET is empty on deploy and only populated when someone uses the feature.

## Kill criterion

If anything in file-sharing regresses during review or staging, revert this PR. The feature flag alone doesn't protect against accidental breakage of `signaling.py` — the new validators MUST NOT perturb the existing `("file", "host")` / `("file", "guest")` dispatch.
