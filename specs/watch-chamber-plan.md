# Watch chamber — phase plan (kickoff)

**Phase:** C, first chamber
**Status:** Planning
**Depends on:** Phase B (Screen) — session_kind registry, RoomTransport, auth validator registry, PeerDataConnection media-track surface are all live on main.

## Goal

"Watch together, perfectly synced." One host queues a video (a URL or a local file), N guests see it play back in lock-step with sub-100 ms drift, and shared play/pause/seek controls propagate over the existing signaling channel. End-to-end encrypted at the transport layer, peer-to-peer where possible, same revolver chamber and backend pattern as Screen.

## What's fundamentally different from Screen

- **Source of bytes.** Screen = browser's own display capture. Watch = an external video (URL the host types in, or a local file the host streams). The host is authoritative for the playback clock; guests are slaves.
- **Control plane.** Screen only has "share / stop". Watch needs play, pause, seek, buffering/ready signals, and "someone's lagging, let's all wait" — a small synchronization state machine.
- **Durability.** Screen is ephemeral (stop = gone). Watch sessions might survive the host briefly tabbing away or reloading — not in the MVP, but the protocol should not make that impossible.

## Gold-standard references

| Ref | What we take |
|---|---|
| Syncplay | Simplest possible sync protocol — "host declares the master clock, guests follow with jitter buffer". We'll copy the 3-message shape (state, chatState, list). |
| Matroska (mkv) chapter atoms | How to model "chapter markers" so guests can jump to per-segment points without the host clicking seek. |
| Jellyfin SyncPlay | Shows the edge cases (paused-on-load, late joiner catches up, drift correction). |

**Not referencing:** Twitch / YouTube live — they are server-authoritative CDN architectures. We are P2P.

## Session model (backend)

Extend `SESSION_KINDS` with `"watch"`. New `ChannelData` fields:

```python
watch_source_url: str | None = None     # http(s) URL the host is playing; None if local file
watch_source_kind: str = "url"          # "url" | "local" — local means host streams the file over DC
watch_started_at: str | None = None     # ISO-8601
```

Invite-token model reused bit-for-bit from Screen (`file-sharing:watch:invite:{slug}`). Rationale: two chambers, identical invite mechanics → proven pattern, zero new auth surface.

## PR-by-PR breakdown (mirrors Screen)

| PR | Title | Scope |
|---|---|---|
| **9** | Watch session backend | `session_kind="watch"` + ChannelData fields + validators + 4 endpoints (`POST /session`, `POST /session/{slug}/invite`, `GET /session/{slug}`, `DELETE /session/{slug}`). Feature-flag `FILE_SHARING_WATCH_ENABLED`. |
| **10** | Sync protocol over DataChannel | Define the 3-message sync payload (`state`, `ready`, `seek`) serialized as JSON on the existing `PeerDataConnection`. No media-track changes; tracks are not used for Watch. Add a typed `SyncMessage` union and a minimal host → guest orchestrator. |
| **11** | Watch UI + chamber integration | `/watch` host page (paste URL → session → broadcast play/pause/seek), `/watch/[slug]` guest page (invite token → follow sync), `<video>` element wired to the sync state machine. Mark Watch as `live` in chambers.ts. |
| **12** | Local-file streaming over DC | For `watch_source_kind="local"`, chunk the file and stream it over the PeerDataConnection's existing binary framing (same path file-sharing uses). Guests buffer and play. This is the heaviest PR — defer until 9-11 have soaked. |

PR 12 is optional for Watch v1; URL-only is already a meaningful product. Ship 9-11 first, decide on 12 after telemetry.

## Sync protocol sketch

Three JSON messages over the existing DataChannel:

```ts
type SyncMessage =
  | { t: 'state'; playing: boolean; position: number; at: number }  // host → guest
  | { t: 'ready'; position: number }                                // guest → host
  | { t: 'seek'; position: number }                                  // host → guest
```

- `state.at` is `performance.now()` on the host at send time. Guests compute drift against `performance.now()` on receive to correct playback rate within a tolerance window (±50 ms) before issuing visible seeks.
- `ready` lets the host hold play until the slowest guest has buffered. Default: wait up to 2s for all, then play regardless.
- No bandwidth estimation, no ABR. URL playback leans on the browser's native buffering; the sync layer just corrects the clock.

## What's explicitly out of scope for Phase C v1

- No recording / rewind after session ends.
- No chat overlay — that's the Collab chamber.
- No subtitle sync — guest's browser handles its own tracks from the URL.
- No DRM / encrypted-source playback.
- No voting on "next video" — host is sole authority.

## Risk

Medium-high. Unlike Screen (where the browser's WebRTC stack does the heavy lifting), Watch sync is logic we write. The clock drift math + buffer coordination has real failure modes. Mitigations:

- Start URL-only (PR 11). Local-file streaming (PR 12) has 10x the surface area.
- Feature flag stays off until the drift tolerance is measured on real networks.
- Kill criterion: if file-sharing or screen regress, revert. PR 9-11 must not touch file-sharing code paths, same as PR 5-7 didn't.

## First commit target

PR 9 mirrors Screen's PR 5 exactly — same module layout (`sharing/watch/`), same feature-flag pattern, same validator registration, same Redis invite-token model. Estimated ~1500 LOC + ~40 tests, same order of magnitude as PR 5.

## Kill criterion for the phase

If Watch sync consistently drifts >500 ms on same-LAN connections across the three most common browsers (Chrome, Firefox, Safari), rethink the architecture before shipping. The product promise is "perfectly synced" — missing the target by an order of magnitude kills the category, not just the feature.
