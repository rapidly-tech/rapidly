# Call chamber — phase plan (kickoff)

**Phase:** D, first chamber
**Status:** Planning
**Depends on:** Phase B (Screen) — `PeerDataConnection.addTrack` already
exists and does exactly what Call needs. Phase C (Watch) not required.

## Goal

"Encrypted voice + video for 1:1 and small groups." Two to four
participants join a room, browsers capture their camera+mic with
`getUserMedia`, and everyone's tracks flow peer-to-peer over the same
PeerDataConnection transport Screen uses. End-to-end encrypted at the
DTLS/SRTP layer, same feature-flag rollout, same revolver chamber
pattern.

## What's different from Screen

- **Every participant publishes.** Screen has one host; Call is fully
  symmetric. N×(N−1) peer connections at worst, which bounds us at ~4
  before bandwidth hurts.
- **Bidirectional media.** Screen's PR 6 media-track surface is
  symmetric already — `addTrack` works the same on both sides. The
  novelty is just that guests call it too.
- **getUserMedia permissions.** Camera + mic permission dialogs on
  both sides, not just the host. Need a graceful denied-permission
  state.

## What reuses Phase B+C wholesale

- `SESSION_KINDS` registry, `ChannelData`, invite-token model, 4
  endpoints, feature-flag pattern — lift verbatim from Screen/Watch.
- `PeerDataConnection.addTrack` + `onTrack` — the exact surface we
  built in PR 6. No changes.
- Signaling validator registry — one `("call", "host")` and one
  `("call", "guest")`.
- `sanitizeVideoUrl`-style client/server defense-in-depth pattern —
  N/A here because Call doesn't take a URL, but the same
  "belt-and-suspenders" discipline applies to the session params we do
  accept.

## Gold-standard references

| Ref | What we take |
|---|---|
| LiveKit | Track-publication API shape. We keep our narrower primitive but match their idioms where possible. |
| matrix-js-sdk MatrixCall | How to model participant state + device changes mid-call. |
| mediasoup (demo) | Mesh vs SFU trade-off analysis — we ship mesh for v1, SFU is a separate project if/when it matters. |

**Mesh vs SFU:** v1 is mesh (every participant has a DC to every other).
Bandwidth is N² per participant. Hard-cap at 4 concurrent participants
in config so the mesh never melts a home uplink. SFU / relay server is a
Phase E+ decision, not a v1 blocker.

## Session model (backend)

Extend `SESSION_KINDS` with `"call"`. Add:

```python
call_mode: str = "audio_video"  # "audio_only" | "audio_video"
max_participants: int = 4         # separate cap from max_viewers
call_started_at: str | None = None
```

Invite-token model reused bit-for-bit. Redis key:
`file-sharing:call:invite:{slug}`.

The host-secret concept still exists — the session creator holds the
secret, anyone else needs an invite token. Terminologically we may
prefer "moderator" over "host" on the UI since every participant
publishes, but on the wire the roles stay `host` and `guest` for
consistency with the existing auth-validator registry.

## PR-by-PR breakdown (mirrors Screen/Watch)

| PR | Title | Scope |
|---|---|---|
| **13** | Call session backend | `session_kind="call"`, 4 endpoints, 2 validators, Redis invite tokens, `FILE_SHARING_CALL_ENABLED` flag. Clone of PR 9. |
| **14** | N-way participant mesh wiring | Client-side coordinator that opens a DC to every other participant announced via signaling. Reuses PR 6 `addTrack` / `onTrack`. |
| **15** | Call UI — `/call` lobby + `/call/[slug]` room, participant grid, mute/camera toggles, copy-invite. Mark Call as `live` in chambers.ts. |

**No PR 12-style "optional local-file" variant.** Call is simpler than
Watch because there's no external source — everything is
`getUserMedia`.

## Media-device handling

Each browser session picks default devices on mount and surfaces a
small picker (mic / camera / speaker). Device changes mid-call are
handled by replacing the track on every open PeerDataConnection via
the sender's `replaceTrack` — already supported by the browser on the
same RTCRtpSender PR 6 gave us access to, no new client code needed
beyond the selection UI.

## What's explicitly out of scope for v1

- No SFU / server-relayed media. Mesh caps at 4 participants.
- No recording.
- No screen-within-call (that's Screen plus Call — future
  composability).
- No background blur / noise suppression — browser `MediaTrack`
  constraints handle the basics.
- No in-call chat — that's the Collab chamber.
- No ringing / calling notifications — the invite-link model stands
  in for that. You send a link, they click it.

## Sync / coordination

No host-authoritative clock (unlike Watch). Call doesn't need playback
sync — each participant's tracks are independent real-time streams.
The coordinator's only job is "when someone joins, open a DC to them;
when someone leaves, close the DC". The signaling server's existing
`participant-joined` / `participant-left` frames (already used by
Screen for viewer-count) cover that.

## Risk

Medium. The hardest unknowns are not Call-specific — they're WebRTC
stack behaviour we've already validated with Screen + Watch:

- ICE traversal through NAT.
- TURN relay fallback.
- Simulcast / ABR under bandwidth constraints.

Things that are genuinely new:

- Two-way `getUserMedia` permission flows on every participant's
  browser. Need explicit denied-permission states.
- Mesh scaling — 4 participants = 12 simultaneous peer connections
  across the room (N × (N-1) × 2 if audio and video are separate
  transceivers). Measure on real hardware before opening cap.

## Kill criterion for the phase

If a 4-participant mesh on same-LAN exhibits audible dropouts or
>150 ms glass-to-glass latency across the three common browsers, stop
and reconsider the mesh-vs-SFU decision before shipping. We promised
"encrypted voice + video for 1:1 and small groups" — missing on
latency or quality kills the category.

## First commit target

PR 13 is a clone-and-sed of Watch PR 9. Estimated ~1500 LOC + ~40
tests. If the Screen→Watch pattern holds, this should take less effort
each time: PR 5 → PR 9 was faster than PR 5 alone because so much
infrastructure was in place. PR 13 should be faster still.
