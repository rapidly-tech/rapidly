# Spec: Screen chamber — media tracks on `PeerDataConnection` (PR 6)

**Phase:** B, PR 6 (second Phase B PR; depends on PR 5 #48)
**Status:** Draft → Implemented in this commit
**Related:** PR 5 (screen session backend, merged), PR 7 (UI + revolver landing, follow-up)

## Goal

Extend `PeerDataConnection` so a host can publish one or more `MediaStreamTrack`s (screen video + optional audio) and guests receive them via `ontrack`. The data-channel API stays bit-for-bit compatible so file-sharing flows do not regress.

**Non-goal:** No UI, no hooks, no session glue to the Screen backend — those ship in PR 7.

## Design

### 1. Public surface additions

Adding the minimum surface that maps to the WebRTC primitives without leaking RTC types into calling code:

```ts
/** Host-side: attach a track before calling createOffer(). Tracks attached
 *  after createOffer() require renegotiation (see section 3).                */
addTrack(track: MediaStreamTrack, stream: MediaStream): RTCRtpSender

/** Host-side: remove a previously attached track. Fires renegotiation if the
 *  connection is already established.                                       */
removeTrack(sender: RTCRtpSender): void

/** Host-side: current list of local senders (so the caller can build a
 *  MediaStream for the local preview if it wants).                          */
getLocalSenders(): readonly RTCRtpSender[]

/** Guest-side callback: fired when the remote peer adds a track. The
 *  streams array is the RTCTrackEvent.streams payload (one stream per
 *  source today; future chambers may use multiple).                         */
onTrack: ((track: MediaStreamTrack, streams: readonly MediaStream[]) => void) | null
```

Everything else on the class (`send`, `onData`, `onOpen`, `onClose`, `onError`, `close`, `createOffer`, `handleOffer`, `handleAnswer`, `handleIceCandidate`) stays untouched.

### 2. Offer/answer flow

`pc.addTrack()` mutates the local SDP, so tracks **must** be attached before `createOffer()`. The existing `createOffer()` already calls `pc.createOffer()` after the data channel exists — we just need callers to `addTrack()` first. No code change inside `createOffer()`; we rely on the documented ordering.

Guest side: `this.pc.ontrack = (event) => this.onTrack?.(event.track, event.streams)` registered in the constructor. This delivers tracks the moment the remote description is set, regardless of who added them.

### 3. Mid-session renegotiation

If a host calls `addTrack` / `removeTrack` after the initial offer is answered, the connection needs a fresh SDP exchange. Minimal support in this PR:

- Register `pc.onnegotiationneeded` once in the constructor.
- When it fires **and** the connection is already established, call `_renegotiate()`:
  1. `pc.createOffer()` → `pc.setLocalDescription()`.
  2. Send the new SDP over signaling with `type: "offer"` (same message shape the initial handshake uses — the wire protocol already supports multiple offers).
- Guest side handles the subsequent `handleOffer()` exactly as today; the re-answer goes back over signaling. No new message types.

This keeps the signaling contract unchanged. The server does not need to know a renegotiation happened — it just relays the offer/answer messages.

### 4. Track cleanup on `close()`

`close()` must stop every local track we own and detach every sender. Without this, the host's camera/screen-capture indicator stays red because the underlying MediaStreamTrack is still live.

```ts
for (const sender of this.pc.getSenders()) {
  if (sender.track) sender.track.stop()
}
```

The call to `this.pc.close()` at the end of `close()` does the rest (removes transceivers, releases ICE allocations).

### 5. ICE candidate handling

Adding media tracks does not change the ICE pipeline — existing buffer/flush logic is unaffected. Tracks may cause more bundled m-lines and therefore slightly more candidates, but each is still sent/received individually via the same `ice-candidate` signaling message.

### 6. What is intentionally excluded from this PR

- **No simulcast / no SVC.** Host publishes one video track at native resolution; future work if quality gets bad.
- **No audio mixing.** If the host attaches an audio track it's delivered as-is.
- **No per-guest muting from the host side.** Host can only stop their own tracks.
- **No stats / quality callback.** `RTCPeerConnection.getStats()` stays reachable via `(pc as any)` if something above needs it; not exposed as a first-class API yet.
- **No fallback to data-channel video.** If WebRTC media fails on a network, the session fails — we don't try to tunnel tracks through the DC.

## Tests (vitest + happy-dom polyfill where possible)

`RTCPeerConnection` is not implemented in happy-dom, so tests that exercise the actual SDP path need a minimal stub. Three coverage groups:

1. **Shape tests** — `PeerDataConnection` exposes `addTrack`, `removeTrack`, `getLocalSenders`, `onTrack` with the right signatures (compile-time + runtime typeof check).
2. **Stubbed-PC tests** — inject a fake `RTCPeerConnection` that records `addTrack` / `getSenders` / fires `ontrack`. Assert:
   - `addTrack` forwards to `pc.addTrack` and returns the sender.
   - `onTrack` fires when the stub emits a synthetic `RTCTrackEvent`.
   - `close()` calls `track.stop()` on every local sender's track.
   - `removeTrack` calls `pc.removeTrack` with the sender.
3. **Renegotiation trigger** — fire the stub's `onnegotiationneeded` after a "connected" state and assert a second `offer` signaling message goes out.

The existing 670-line class has no unit tests today (tested end-to-end through the app). Adding these is a net quality win, even isolated to the new surface.

## Risk

Low: the existing `send` / `onData` / `DataChannel` path is untouched. The only cross-surface risk is the new `pc.onnegotiationneeded` handler — it MUST early-return when the connection is not yet established (otherwise the initial `createOffer()` path double-fires and breaks the handshake). The tests cover that gate.

## Kill criterion

If file-sharing tests regress locally or in CI, revert. Media-track code is additive; reverting it cannot damage file-sharing state because nothing on the hot path of file transfer has changed.
