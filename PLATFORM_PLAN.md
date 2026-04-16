# Rapidly Platform Plan

**Status:** Draft
**Last updated:** 2026-04-17
**Owner:** Engineering

---

## 1. One-sentence summary

Generalize Rapidly's existing file-sharing P2P stack into a reusable transport, add **Screen**, **Messages**, **Call**, **Watch**, and (gated) **Collab** chambers on top, and redesign the landing page as a "revolver" radial selector — so Rapidly reads as a P2P platform, not a single-feature file-transfer app.

---

## 2. Principles (carry through every PR)

1. **File sharing in production never breaks.** Every PR is backwards-compatible. No flag days.
2. **Every refactor earns its keep by having a second customer.** Screen is the first customer of the generalized stack; Messages, Call, Watch follow.
3. **Small PRs.** Each one reviewable in under an hour, deployable on its own.
4. **Clean-room policy.** No third-party feature code in the repo. For every feature: study the reference, write a spec in our words, implement from the spec with the reference closed. (See §8 for references.)
5. **End-to-end encryption at the application layer** for every P2P session, on top of WebRTC's DTLS transport encryption. AES-256-GCM envelopes with ECDH-derived session keys.
6. **Default to looking at Polar (our upstream) first** for any architectural uncertainty.

---

## 3. Platform direction — the six chambers

Rapidly is a P2P platform with six composable capabilities:

| Chamber | Type | What it is | Status |
|---|---|---|---|
| **Files** | primary | Existing P2P file transfer | Live |
| **Secret** | primary | Existing one-time encrypted secrets | Live |
| **Screen** | primary | P2P screen share (`getDisplayMedia` + `addTrack`) | Phase B |
| **Watch** | primary | Synced video watch-party (URL-based v1) | Phase W |
| **Call** | augment | Voice/video — **stacks on any primary** | Phase D |
| **Collab** | primary | Whiteboard (clean-room rewrite) | Phase C (gated) |
| **Messages** | overlay | Universal chat — available in any session | Phase M |

**Composition rule.** Exactly one primary chamber is active at a time. Call and Messages can layer on top of any primary.

### 3.1 Landing page — "revolver" UI (Variant A)

```
                ╭── FILES ──╮      ← lit = active
              ●               ●          white = primary mode
       SECRET                     SCREEN        (one at a time)
              ╭────────────╮
              │            │         glow = layered on
              │   CENTER   │          emerald = augment
              │            │          (stacks on primary)
              ╰────────────╯
       WATCH                     COLLAB
              ●               ●
                ╰── CALL ──╯
```

- Click-to-jump with a short spin animation.
- Mobile: collapses to a horizontal scrollable strip above the form.
- Messages is a persistent chat chip inside the center area, not a chamber.

---

## 4. Phase A — Generalize the P2P stack (4 PRs, no user-visible change)

Every PR here keeps file sharing working identically. File sharing is tested continuously throughout.

### PR 1 — Add `session_kind` to the channel model

**Goal:** Make `ChannelData` describe what kind of session it is without breaking existing Redis entries.

**Files**
- `server/rapidly/sharing/file_sharing/queries.py` — `ChannelData` (lines 104–149).

**Changes**
- Add field `session_kind: str = "file"` to `ChannelData`.
- In `ChannelData.from_dict`, default to `"file"` when the key is missing (existing Redis entries read back as file sessions, no migration).
- Make file-specific fields (`file_name`, `file_size_bytes`, `max_downloads`, `price_cents`, `is_paid`, `reader_token`) `Optional` at the type level.
- Add module-level `SESSION_KINDS = {"file"}` set; extend as new kinds register.
- Serialization guard: `session_kind="file"` still requires the file fields.

**Tests**
- Round-trip `ChannelData` without `session_kind` → reads as `"file"`.
- Round-trip with `session_kind="screen"` → survives to_dict/from_dict.
- Existing file-sharing tests pass unchanged.

**Rollout:** Normal deploy. No flag, no migration.
**Risk:** Very low — pure widening.

---

### PR 2 — Lift P2P transport out of the file-sharing namespace

**Goal:** Stop pretending the transport code is file-specific.

**Files moved (no logic change)**
- `clients/apps/web/src/utils/file-sharing/peer-connection.ts` → `utils/p2p/peer-connection.ts`
- `clients/apps/web/src/utils/file-sharing/signaling.ts` → `utils/p2p/signaling.ts`
- `clients/apps/web/src/utils/file-sharing/ws-relay.ts` → `utils/p2p/ws-relay.ts`
- **Split** `utils/file-sharing/constants.ts`:
  - Generic transport constants (`BUFFER_THRESHOLD`, `MAX_FRAME_SIZE`, `MAX_HEADER_SIZE`) → `utils/p2p/constants.ts`
  - File-specific (`FILE_SHARING_SIGNAL_PATH`) stay.

**Changes**
- `SignalingClient.connect()` takes the signal path as a parameter instead of importing `FILE_SHARING_SIGNAL_PATH`.
- All existing callers in `utils/file-sharing/*` update imports.

**Tests:** TypeScript + existing frontend tests. Zero logic change.
**Rollout:** Normal deploy.
**Risk:** Low — mechanical move, tsc catches any miss.

---

### PR 3 — Generalize signaling roles & auth dispatch

**Goal:** Decouple `signaling.py` from file-sharing-specific auth so new session kinds can register their own validators.

**Files**
- `server/rapidly/sharing/file_sharing/signaling.py`
  - `_authenticate` (lines 317–416)
  - `Peer` (line 92)
  - `handle_signaling` (line 587)
  - `_handle_webrtc_signaling` (role check line 574)
- `clients/apps/web/src/utils/p2p/signaling.ts` — `connect()` signature (line 65).

**Changes**

1. **Role rename (backwards-compatible).** Introduce `host` / `guest` as canonical values. Server accepts `uploader`|`host` and `downloader`|`guest` for one release window; then drop the old names.
2. **Auth-validator registry.**
   ```python
   AuthValidator = Callable[
       [WebSocket, str, str, ChannelData, dict], Awaitable[bool]
   ]
   _AUTH_VALIDATORS: dict[tuple[str, str], AuthValidator] = {}
   def register_auth_validator(session_kind, role): ...
   ```
   Existing file-sharing secret/reader-token/payment-token logic moves verbatim into two registered validators: `("file", "host")` and `("file", "guest")`.
3. `_authenticate` becomes thin:
   ```python
   validator = _AUTH_VALIDATORS.get((channel.session_kind, role))
   if not validator or not await validator(ws, slug, role, channel, msg):
       await _send_error(ws, "Authentication failed")
       ...
   ```
4. Rename `room.uploader_id` → `room.host_id`. Update the "one uploader per room" check (line 624) and the `connect-request` default routing (line 535).
5. Widen `SignalingClient.connect()` role type to `string` with a union; compat shim keeps existing callers working.

**Tests**
- Each registered validator in isolation against FakeRedis.
- Full file-sharing upload/download integration test against the refactored server.
- Reject on unknown `session_kind`.

**Rollout:** Normal deploy; compat shim keeps older clients working across the server roll.
**Risk:** Medium — signaling is the hot path. Mitigation: compat shim + extensive integration tests.

---

### PR 4 — Redis pub/sub for cross-worker signaling

**Goal:** Kill the single-worker deployment constraint. Prerequisite for every long-lived session kind.

**Files**
- `server/rapidly/sharing/file_sharing/signaling.py`
- New: `server/rapidly/sharing/file_sharing/signaling_transport.py`

**Changes**

1. **Transport abstraction.**
   ```python
   class RoomTransport(Protocol):
       async def register_peer(slug, peer_id, role) -> None: ...
       async def unregister_peer(slug, peer_id) -> None: ...
       async def list_peers(slug) -> list[PeerRef]: ...
       async def get_host_id(slug) -> str | None: ...
       async def send_to_peer(slug, peer_id, message) -> None: ...
       async def subscribe_messages(slug, peer_id) -> AsyncIterator: ...
   ```

2. **In-memory impl** — current `SignalingManager` behavior unchanged.

3. **Redis impl.**
   - Room membership: `file-sharing:p2p:room:{slug}:peers` (hash) — `{peer_id: json(role, worker_id, relay_mode)}`. TTL = `MAX_CONNECTION_LIFETIME`.
   - Host index: `file-sharing:p2p:room:{slug}:host` (string, peer_id).
   - Per-peer inbox: PUBSUB channel `file-sharing:p2p:peer:{peer_id}`. Owning worker subscribes for its local peers.
   - Binary frames: published as bytes.
   - `send_to_peer` = `PUBLISH file-sharing:p2p:peer:{peer_id} <payload>`.
   - Rate/byte counters move to a `file-sharing:p2p:room:{slug}:meta` hash, Lua-atomic.

4. **Worker lifecycle.** On peer register → SUBSCRIBE. On unregister/close → UNSUBSCRIBE + HDEL.

5. **Feature flag.** `FILE_SHARING_SIGNALING_BACKEND=memory|redis` (default `memory`).

**Tests**
- Existing tests run against both backends via parameterization.
- Two peers on different worker processes → full SDP flow e2e.
- Chaos test: kill subscriber mid-transfer; assert reconnect resumes.

**Rollout (staged)**
1. Deploy with flag=`memory`. No change.
2. Staging → flag=`redis`. E2E suite. 48h soak.
3. Prod → flag=`redis`. Keep `--workers 1` for one more week.
4. Scale to `--workers 2` in one pod. 72h observation.
5. Roll out fleet-wide.

**Risk:** Highest in Phase A.
**Kill criterion:** file-sharing error rate rises >0.1% over baseline → flip flag back to `memory`.

---

### 🚦 Phase A → Phase B gate

File-sharing error rate unchanged for 72h after PR 4 is at 100% rollout. Then Phase B starts.

---

## 5. Phase B — Screen chamber (3 PRs, first user-visible new capability)

Screen is chosen as the first new chamber because:
- Uses exactly the same unidirectional topology as file sharing (host → viewers). No SDP refactor needed.
- Fits Rapidly's professional/B2B brand.
- Real demand on Reddit (Screego, Dead Simple Screen Sharing).
- Smallest incremental lift on top of Phase A.

### PR 5 — Register `session_kind="screen"` server-side

**Files**
- `server/rapidly/sharing/file_sharing/queries.py` — optional screen fields.
- New: `server/rapidly/sharing/screen/` (sibling to `file_sharing/`):
  - `actions.py` — `create_screen_session`, invite-token helpers.
  - `api.py` — `POST /v1/screen/session`, `GET /v1/screen/session/{slug}`, `DELETE /v1/screen/session/{slug}`.
  - `types.py` — Pydantic models.
  - `permissions.py`.
- `signaling.py` — register `("screen", "host")` and `("screen", "guest")` validators.

**Schema additions on `ChannelData`** (all Optional):
```python
max_viewers: int = 0       # 0 = unlimited; default 10
screen_started_at: str | None = None
```

**Auth**
- Host: channel secret (reuse `_hash_secret`).
- Guests: short-lived invite tokens (`file-sharing:screen:invite:{slug}` SET, hashed).

**API**
- `POST /v1/screen/session` → `{short_slug, long_slug, secret, host_invite_url, guest_invite_template}`.
- `POST /v1/screen/session/{slug}/invite` → mint guest invite (requires secret).

**Config flag:** `FILE_SHARING_SCREEN_ENABLED=false` initially.

**Risk:** Low — purely additive.

---

### PR 6 — Extend `PeerDataConnection` with media-track support

**Files**
- `clients/apps/web/src/utils/p2p/peer-connection.ts`.

**Changes (additive)**
- New method: `addMediaStream(stream: MediaStream)` — adds tracks via `pc.addTrack()`.
- New event: `onTrack(handler)` — wraps `pc.ontrack`.
- Data channel stays for control messages (start/stop, viewer count).
- No change to existing `send`/`onData` API.

**Reference (study-only):** MDN `RTCPeerConnection.addTrack`, `RTCRtpSender`, and LiveKit's TS client wrapping pattern.

**Tests**
- Unit: attach a fake MediaStream; assert track events propagate.

**Risk:** Low — strictly additive.

---

### PR 7 — Screen-share UI

**Files**
- New page: `clients/apps/web/src/app/(main)/(website)/(landing)/screen/page.tsx` (host flow).
- New page: `clients/apps/web/src/app/screen/[slug]/page.tsx` (guest flow).
- New component: `clients/apps/web/src/components/Screen/ScreenRoom.tsx`.
- New hooks:
  - `useScreenHost(slug, secret)` — `getDisplayMedia` + broadcast.
  - `useScreenGuest(slug, inviteToken)` — receive track, attach to `<video>`.

**Flow**
1. Host opens `/screen`, clicks "Start screen share".
2. Browser prompts for `getDisplayMedia` (screen/window/tab).
3. Backend creates `session_kind="screen"` channel. Host gets invite URL template.
4. Guest opens invite URL → WebSocket auth → WebRTC connect → `<video>` gets the track.

**Deliberate v1 limits** (documented in UI)
- Max 10 viewers per session.
- 6-hour cap (existing `MAX_CONNECTION_LIFETIME`).
- No drawing/annotation overlay (v2).
- No built-in chat (use Messages overlay once Phase M lands).

**Tests**
- Playwright: host shares, guest joins, receives track, ends session.

**Rollout:** Behind `FILE_SHARING_SCREEN_ENABLED` flag. Dark ship → internal → small beta → public.

**Risk:** Low — isolated.

---

### 🚦 Phase B also ships the landing page

The revolver landing page (Variant A, 6 chambers, click-to-jump) ships *before* PR 7 goes public. Flow:
- Chamber 1 (Files) — live, opens existing file-sharing flow.
- Chamber 2 (Secret) — live, opens existing secret flow.
- Chamber 3 (Screen) — "Coming soon" until PR 7 flips the flag.
- Chambers 4–6 (Watch, Call, Collab) — "Coming soon" with waitlist email capture.

**Files**
- `clients/apps/web/src/components/Landing/Revolver/` (new).
- `clients/apps/web/src/app/(main)/(website)/(landing)/page.tsx` — swap hero for the revolver.

**Metadata & copy update** (in the same PR):
- Title / OG: "Rapidly — Private P2P for the browser."
- Description: "Encrypted file transfer today. Screen sharing next. Never on our servers."
- `siteName: 'Rapidly'` (currently 'File Sharing').

---

## 6. Phases M / D / W — the remaining capabilities

### Phase M — Messages (E2E chat overlay)

**Goal:** Persistent chat chip available in any session. Not a chamber; a universal affordance.

**Scope**
- Backend: chat messages are ephemeral, sent only over the existing P2P data channel. No server storage. (Optional: session-scoped Redis buffer for late-joiner backfill, 24h TTL.)
- Frontend:
  - New: `clients/apps/web/src/utils/p2p/messages/` — wire protocol + envelope crypto.
  - New: `clients/apps/web/src/components/Messages/ChatPanel.tsx` — sliding panel with input + history.
- Crypto: ECDH at session start → shared session key → AES-256-GCM envelopes with monotonic counter nonce. Same primitives as `utils/file-sharing/encryption.ts`.

**References**
- Transport pattern: [leonh/redis-streams-fastapi-chat](https://github.com/leonh/redis-streams-fastapi-chat) (351⭐ MIT).
- Crypto spec (not code): [Signal Protocol](https://signal.org/docs/) X3DH + Double Ratchet.

**Estimate:** 2–3 weeks.
**Risk:** Medium — crypto takes time to do right. Mitigation: v1 uses basic ECDH + AES-GCM; Double Ratchet is v2.

---

### Phase D — Call (voice/video augment)

**Goal:** Add voice and optional video to any primary session.

**Prerequisite refactor:** `PeerDataConnection` becomes symmetric — either peer can call `createOffer`. Today uploader-only (`peer-connection.ts:133`).

**Scope**
- Backend: no new session kind needed — Call is an augment layered on an existing session. Auth reuses existing session's auth.
- Frontend:
  - Extend `PeerDataConnection` for symmetric SDP + audio/video tracks.
  - New: `clients/apps/web/src/components/Call/CallTray.tsx` — mute/unmute, camera toggle, hang up.
  - Handle echo cancellation, noise suppression (browser-default).

**References**
- [LiveKit](https://github.com/livekit/livekit) (Apache-2.0) — SDP patterns, track management.
- [mediasoup](https://github.com/versatica/mediasoup) (ISC) — authoritative SDP negotiation reference.

**Estimate:** 2 weeks.
**Risk:** Medium — symmetric SDP is the one non-trivial refactor in the plan.

---

### Phase W — Watch (URL-based synced playback)

**Goal:** Host pastes a video URL; guests watch in sync.

**Scope**
- Backend: new `session_kind="stream"` with `stream_source_url`, `stream_source_kind`, `max_viewers`.
- Frontend:
  - New: `clients/apps/web/src/utils/p2p/stream-protocol.ts` — `{type:'play'|'pause'|'seek'|'heartbeat'}` messages.
  - Sync controller: host authoritative; guest adjusts `<video>.currentTime` on drift >250 ms.
  - Supported sources v1: direct MP4/WebM URLs. **No YouTube** (ToS), **no DRM** (EME).
  - HLS support via our own lightweight m3u8 parser (study `hls.js`, implement the subset we need).

**References**
- [kyle8998/Vynchronize](https://github.com/kyle8998/Vynchronize) (1.1k⭐ MIT) — protocol only, study the sync loop.

**Estimate:** 2 weeks.
**Risk:** Low — isolated application-layer logic on well-tested transport.

---

### Phase C — Collab / Whiteboard (**gated bet**)

**Goal:** Excalidraw-class whiteboard, built entirely from scratch in our architecture. 100% clean-room — no third-party canvas code in the repo.

**Gate.** Only begin Phase C after 30 days of Phase W or Phase B live traffic proves platform-side engagement. Otherwise delay and use time for customer-facing polish.

**Scope**
- Canvas engine: shape tools (rect, ellipse, arrow, line, text, pen), selection, move, resize, delete, undo/redo.
- Hand-drawn rendering: reimplement rough.js-style seeded-random strokes (~300 LOC).
- Export: PNG + SVG.
- Collaboration: last-writer-wins per-element timestamps (~200 LOC). Upgrade to CRDT only if conflicts become real.
- Persistence: drawings stored in Redis via existing `ChannelRepository` pattern.

**References (study only, clean-room)**
- **Primary:** [excalidraw/excalidraw](https://github.com/excalidraw/excalidraw) (121k⭐ MIT). Canvas engine, shape model, collaboration protocol.
- **Simplified study target:** [mirayatech/NinjaSketch](https://github.com/mirayatech/NinjaSketch) (447⭐, **⚠️ no license** — eyes-only).
- **Architecture only:** [tldraw/tldraw](https://github.com/tldraw/tldraw) (46k⭐, **⚠️ custom license** — never copy).
- **CRDT (only if needed):** [Yjs](https://github.com/yjs/yjs) (21k⭐, ⚠️ custom license — study docs, never copy).

**Estimate:** 3–6 months (canvas engineering is expensive).
**Risk:** High. Kill criterion: if after 6 weeks of spec+implementation MVP can't render/sync basic shapes, descope to "shared image + annotations" chamber instead.

---

## 7. Timeline, gates, and kill criteria

| Week | Phase | Deliverable |
|---|---|---|
| 1 | A (PR 1, 2) | Model + transport folder refactors merged. |
| 2 | A (PR 3) | Signaling validator registry live. |
| 2–3 | A (PR 4) | Redis signaling behind flag → staging soak. |
| 3 | A rollout | Prod flipped to `redis`. 72h observation. |
| 4 | B (PR 5–6) | Screen session API + PC media-track support. |
| 4 | B landing page | Revolver UI ships with 3 "coming soon" chambers. |
| 5 | B (PR 7) | Screen-share UI → internal beta. |
| 6 | B public | Screen chamber live. |
| 7–9 | M | Messages overlay + E2E crypto. |
| 10–11 | D | Call (symmetric SDP + tracks). |
| 12–13 | W | Watch (URL-based sync). |
| **Gate: 30 days traffic data.** | | Decide on C. |
| 14+ | C (if greenlit) | Collab — 3–6 month project. |

**Kill criteria**
- **Phase A (PR 4):** file-sharing error rate >0.1% over baseline during rollout → flip `memory` flag.
- **Phase B:** if Screen has <100 distinct sessions from non-team accounts after 30 days, pause M/D/W marketing and reassess.
- **Phase C:** if MVP can't render/sync basic shapes after 6 weeks → descope to "shared image + annotations."

---

## 8. Clean-room research workflow

For every feature, repeat this cycle:

1. **Audit pass (~1 day).** Read the reference top-to-bottom. Write a prose spec in our own words covering: data model, message protocol, critical algorithms, edge cases. **No code written.** Output: `docs/specs/<chamber>.md`.
2. **Architectural fit (~½ day).** Map spec onto our conventions: which `api.py`/`actions.py`/`queries.py` functions, which Redis keys, which `utils/p2p/*` module. **Still no code.**
3. **Clean-room implement (main time budget).** Write from the spec, in our conventions. The reference repo stays closed.
4. **Validate (~1 day).** Test real scenarios. Bugs → back to step 1 for that piece only.

### Reference discipline

- **Apache-2.0 / BSD / ISC / MIT** → safe to study, still never copy under clean-room.
- **AGPL / GPL / custom / no-license** → study architecture only, never look at specific implementations.
- Internal docs and commit messages may cite "inspired by X" for engineering provenance.
- User-facing surfaces (UI, marketing, domain, customer docs) never mention references.

---

## 9. Reference repos (audited)

### Gold-standard tier — check first for any architectural question

| Project | URL | License | Why |
|---|---|---|---|
| **Polar.sh** (our upstream) | https://github.com/polarsource/polar | Apache-2.0 | Same code patterns — we forked from this |
| LiveKit | https://github.com/livekit/livekit | Apache-2.0 | Production WebRTC SFU |
| mediasoup | https://github.com/versatica/mediasoup | ISC | Most rigorous WebRTC engine in OSS |
| matrix-js-sdk | https://github.com/matrix-org/matrix-js-sdk | Apache-2.0 | Industrial E2E messaging |
| Synapse | https://github.com/element-hq/synapse | AGPL-3.0 ⚠️ | Matrix server patterns (study only) |
| Yjs | https://github.com/yjs/yjs | ⚠️ custom | CRDT reference (study only) |
| Tailscale | https://github.com/tailscale/tailscale | BSD-3 | P2P networking philosophy |

### Per-chamber references (credibility-audited)

| Chamber | Reference | Credibility |
|---|---|---|
| Screen | aiortc (5k⭐ BSD-3) + MDN + our `PeerDataConnection` | 🟢 solid |
| Messages | leonh/redis-streams-fastapi-chat (351⭐ MIT) + Signal spec | 🟢 solid |
| Call | LiveKit + mediasoup + aiortc | 🟢 solid |
| Watch | kyle8998/Vynchronize (1.1k⭐ MIT) | 🟢 solid |
| Collab | excalidraw (121k⭐ MIT) + NinjaSketch (eyes-only) + tldraw (architecture only) | 🟢 with discipline |

### Rejected (don't re-suggest)

- ❌ `Lucas-Steinmann/webrtc_fastapi_demo` — 3⭐ toy
- ❌ `rykroon/webrtc-signal-server` — abandoned, no license
- ❌ `matacoder/p2p-video-calling-app` — abandoned, no license
- ❌ `MohdSakib535/FastApi_WebRTC` — brand-new personal repo, 0⭐

---

## 10. Out of scope (explicitly)

- **Watch v2 (paste-a-file-from-disk with MSE streaming)** — defer until Watch v1 has usage data.
- **Mesh fan-out** (guests relay to other guests) — v3 only.
- **Screen annotation overlay** — v2 of Screen.
- **Multi-audio / subtitles / DRM** — never on this roadmap.
- **YouTube embed** — YouTube ToS forbids ad-stripping; out of scope permanently.
- **Paid watch parties / paid calls** — revisit only after free versions have traction.

---

## 11. Open questions

1. **Who owns the canvas engine for Phase C?** Canvas/graphics engineering is a specific skill. If no one on the team, Phase C is effectively blocked regardless of policy.
2. **Stream v1 source scope:** direct MP4/WebM only, or also HLS (adds ~1 week)?
3. **Messages persistence:** ephemeral only, or 24h Redis buffer for late-joiner backfill?
4. **Revolver landing copy:** one-line taglines per chamber — who drafts?
5. **Billing story:** does the platform pitch change anything about pricing?

---

## 12. First concrete action

**PR 1** — add `session_kind` to `ChannelData` in `server/rapidly/sharing/file_sharing/queries.py`. Zero risk, zero user impact, unblocks everything else in Phase A.

---

## 13. Definition of Done — the per-PR checklist

**No PR merges without this checklist stamped into its description and all boxes ticked.** The references and quality properties listed in §8–9 are only useful if enforced on every change.

### A. Reference audit (before writing any code)

- [ ] **Polar upstream searched** for prior art on this exact problem (`gh api search/code ... org:polarsource`). If they solved it, port their approach first.
- [ ] **Chamber reference read** — the relevant gold-standard repo (LiveKit for Screen/Call, matrix-js-sdk for Messages, Vynchronize for Watch, Excalidraw for Collab) opened and its handling of this problem summarized in §13.E of the PR description.
- [ ] **Spec written first** at `docs/specs/<feature>.md` — prose-only, no code, covering data model, message protocol, critical algorithms, edge cases.
- [ ] **Reference code closed** while implementing. No copy-paste, no "just peek."

### B. The 7 Rapidly code-quality properties (from §11)

1. [ ] **Security invariants stated in comments** where non-obvious (`# Fails closed on Redis errors...`, `# Uses hmac.compare_digest for constant-time comparison`, `# Atomic via Lua to prevent TOCTOU...`).
2. [ ] **Multi-step Redis state uses Lua scripts**, not a sequence of GET/SET calls. New Lua scripts declared in `redis_scripts.py` with a docstring describing their atomicity guarantee.
3. [ ] **Rate limiting fails closed** on Redis errors (pattern from `_check_ws_connection_rate`). Every new rate-limit entrypoint rejects during Redis outages rather than allowing unmetered traffic.
4. [ ] **Explicit WebSocket close codes** with documented meaning, if touching signaling. Reuse existing codes (4001 invalid, 4003 forbidden, 4008 timeout, 4009 duplicate, 4029 rate-limit, 4010 reported, 4503 service-unavailable). New codes added to a single source-of-truth docstring.
5. [ ] **Backpressure + reassembly handled in the transport layer**, not pushed to callers. If touching `PeerDataConnection` or a new transport module, confirm `bufferedAmountLowThreshold` handling and fragment reassembly are internal to the class.
6. [ ] **Types everywhere.** Backend: `dataclass` for internal structures, `Pydantic` at API boundaries. Frontend: strict TypeScript, no `any`, no unchecked casts. No `# type: ignore` without a comment explaining why.
7. [ ] **"Why" comments only.** No "what" comments that restate the code. Every non-obvious decision has a comment referencing the invariant it protects.

### C. Security discipline

- [ ] New crypto uses **AES-256-GCM + ECDH from our existing module** (`utils/file-sharing/encryption.ts`). No `npm install` of a crypto library, no `libsignal`, no `libsodium-wrappers`.
- [ ] Timing-sensitive comparisons use `hmac.compare_digest` (Python) or `crypto.timingSafeEqual` (Node/bun, if ever touched).
- [ ] No secrets in logs (grep your diff for `_log.info` calls that might include a token/secret/auth header).
- [ ] First-message auth on any new WebSocket endpoint (reuse the `_authenticate` pattern).
- [ ] CSP / `APISecurityHeadersMiddleware` extended for any new user-facing route.

### D. Architecture discipline

- [ ] **Backend module layout** follows convention: `api.py` (handlers), `actions.py` (business logic), `queries.py` (DB/Redis), `types.py` (Pydantic), `permissions.py` (auth deps), `workers.py` (Dramatiq if applicable).
- [ ] **Redis keys** prefixed with `file-sharing:` or a new documented prefix. No ad-hoc prefixes.
- [ ] **Channel-kind dispatch** goes through the validator registry (§4 PR 3). No `if session_kind == "file": ... elif session_kind == "screen": ...` ladders outside the registry.
- [ ] **Frontend transport code** lives in `utils/p2p/`, not `utils/<feature>/`. Feature-specific logic consumes the generic transport.
- [ ] **Plain async functions**, not class singletons, for business logic in `actions.py`.

### E. PR description template

Every PR description must include:

```markdown
## References consulted
- Polar upstream search: <findings or "no prior art">
- Chamber reference: <repo> — <1-paragraph summary of how they handle this problem>

## Spec
Link to `docs/specs/<feature>.md` (committed in this PR or a prior one).

## Checklist
A. Reference audit — [ ] all four boxes ticked
B. 7 quality properties — [ ] all seven confirmed
C. Security discipline — [ ] all five confirmed
D. Architecture discipline — [ ] all five confirmed

## Tests
<what was tested and how>

## Rollout
<flag? migration? staged?>

## Risk
<what breaks if this is wrong, kill criterion>
```

**A PR missing this block blocks merge. No exceptions.**

### F. Why this checklist exists

The plan is to build five new chambers (Screen, Messages, Call, Watch, Collab) in clean-room style. Without an explicit ritual, quality drifts — each PR cuts one corner, six months later the codebase looks nothing like the `signaling.py` we started from. The checklist exists so every single PR either matches our code's existing quality bar or explicitly justifies why it can't.

---

## 14. Local-first development workflow

**Every change builds and passes locally before it touches GitHub.** This is the non-negotiable rule alongside §13.

### 14.1 Existing infrastructure (don't rebuild)

| Layer | Command |
|---|---|
| Infra | `cd server && docker compose up -d` |
| Backend | `uv run task api` (port 8000) |
| Backend tests | `uv run task test` / `uv run task test_fast` |
| Backend lint | `uv run task lint_check && uv run task lint_types` |
| Frontend dev | `cd clients && pnpm dev-web` (port 3000) |
| Frontend tests | `cd clients && pnpm test` |
| Frontend lint | `cd clients && pnpm lint && pnpm typecheck` |

### 14.2 Additions required before Phase A lands

**A. Single verify script** — `./verify.sh` at the monorepo root.
Runs (in order, fails fast): backend lint + types + tests → frontend lint + typecheck + tests → e2e.
Must exit 0 before any push.

**B. Playwright e2e harness** — `clients/apps/web/e2e/`.
Configured for two parallel browser contexts so P2P flows can be exercised end-to-end:
- Chromium flags for fake media: `--use-fake-ui-for-media-stream`, `--use-fake-device-for-media-stream`, `--auto-accept-this-tab-capture`.
- Per chamber: `p2p-helpers.ts`, `file-sharing.spec.ts` (initial), then `screen.spec.ts`, `messages.spec.ts`, `call.spec.ts`, `watch.spec.ts` as chambers land.

**C. Optional pre-push hook** — `.githooks/pre-push` runs `./verify.sh`.
Activated per-clone via `git config core.hooksPath .githooks`. Opt-in — no one is forced but everyone has the option.

### 14.3 Manual smoke checklist (things e2e can't catch)

Document at `docs/LOCAL_TESTING.md`. Run before any P2P PR merges:

| Scenario | What to verify |
|---|---|
| Real screen capture | Chrome + Firefox, real `getDisplayMedia`, frames arrive cleanly |
| Audio quality | Real mic both sides, no echo/distortion |
| NAT traversal | Disable TURN, verify P2P still works on same-network peers |
| TURN fallback | Force `iceTransportPolicy:'relay'`, verify it still connects |
| Mobile Safari | Actual iPhone, one of the peers |
| Poor network | DevTools "Slow 3G", assert graceful degradation |

### 14.4 Checklist addition to §13

Extend §13 A (Reference audit) with one more box:

- [ ] **`./verify.sh` passes locally.** (Append to PR description as "✓ local verify passed at <commit>".)

### 14.5 CI expectation

The same `verify.sh` runs on GitHub Actions as the push gate. Local parity is the rule — if it passes locally, it passes in CI. Any delta is a bug in the setup and blocks merge until fixed.
