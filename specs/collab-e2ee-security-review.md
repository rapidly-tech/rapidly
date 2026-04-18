# Collab v1.1 E2EE — author self-review

**Scope:** PRs #78 (crypto primitives), #79 (envelope + handshake),
#80 (URL fragment), #81 (no-downgrade + default-on), #82
(encryption badge).

**Posture:** the author of the code wrote this. It is NOT a
substitute for external review. The purpose is to surface the
assumptions and trade-offs explicitly so a reviewer can focus their
time on the concerns most likely to break.

## Threat model (what this E2EE protects against)

| # | Threat | Protection |
|---|---|---|
| 1 | Passive network eavesdropper | AES-GCM over DTLS (WebRTC) |
| 2 | Rapidly server operator | Master key never sent to server |
| 3 | Link-stripping attacker (intermediary removes `#k=...`) | No-downgrade stance (PR #81) |
| 4 | Garbage / malformed frame from a real peer | Log-and-drop (PR #77 + decrypt-null return) |
| 5 | Tampered ciphertext (bit-flip in transit) | AES-GCM auth tag |
| 6 | Replay of a stored ciphertext frame | **Partially protected (v1.1.1).** Yjs CRDT merge is idempotent so replay is harmless for the doc body. `y-awareness` now carries a per-peer monotonic counter (PR #90) so replayed awareness frames are dropped. Replay across a peer reconnect remains possible for the heartbeat window — see Concerns §2. |

**Explicitly out of scope** (documented in `specs/collab-e2ee.md`):

- Forward secrecy on membership change (requires a ratchet — v1.2).
- Out-of-band identity verification (safety numbers — v1.2+).
- Malicious peer **inside** the session reading others' edits
  (invites are capabilities; this matches v1).

## Design choices — self-scrutiny

### Why HKDF with chamber-name binding
The info string is `collab:sync:v1` (and `collab:awareness:v1`). A
future chamber that reuses the master key pattern cannot accidentally
derive the same sub-key because their info would be
`<other-chamber>:sync:v1`. Test `hkdf.test.ts` ("different chambers
with the same purpose") pins this.

**Risk:** a future engineer adds a new purpose in Collab without
bumping the version, and — via a bug elsewhere — the new purpose
collides with `sync` or `awareness`. Mitigation: the purpose-string
list is tiny (2 entries), and any new one would go through code
review.

### Why fresh IV per send, not per session
AES-GCM nonce-reuse with the same key is catastrophic
(plaintext-recoverable). `encryptGcm` generates a fresh 12-byte
random IV per call. The "fresh-per-call" invariant is test-pinned
in `aes-gcm.test.ts` ("produces a fresh IV per call").

**Risk:** at 2^32 messages on the same key the birthday bound of
random IVs starts producing collisions. 2^32 is ~4 billion
messages. A pathological edit stream at 100 msg/s hits that in ~1.3
years. Mitigation: the room master key's lifetime is bounded by
the session TTL (default 2 h) — the bound is never reached in
practice. Documented in `specs/collab-e2ee.md` §3.

### Why the hello carries a 1-byte capability instead of a JSON object
Minimalism. A 1-byte payload (0x00 plaintext, 0x01 v1) has no parse
path to exploit. A future version that needs more structure can
extend with extra bytes; current decoder reads only `bytes[0]` and
ignores the rest, so forward-compat is free.

**Risk:** a future version needs to express "v1 AND ratchet support"
and might squeeze it into a second byte. That's fine — existing
clients keep reading byte 0 and negotiate v1.

### Why no downgrade from E2EE to plaintext (PR #81)
If `selfHasE2ee`, the provider sends ciphertext regardless of what
the peer advertised. A link-stripping attacker who removes `#k=...`
forces the other side to be plaintext-only; with downgrade allowed,
the keyed side would have silently accommodated them and leaked
plaintext. Without downgrade, the unkeyed side can't decrypt and
the session just doesn't converge. UX pays a cost (confused user),
security wins.

**Risk:** the guest UI surfaces a clear "missing encryption key"
page only when the flag is on (PR #80). If a deployment opts out
with `NEXT_PUBLIC_COLLAB_E2EE=false`, guests with a fragment will
successfully connect but land on a plaintext session — because
neither side opts into E2EE in that configuration. That's the
correct behaviour per the flag but worth re-reading.

### Why static master key (no rotation)
Simplicity. The master is minted per session, dies with the session.
No re-invite, no key-sync-on-peer-leave, no ratchet state to track.

**Risk:** a peer who leaves still has the master and could re-join
if the invite token is stolen. The invite token is the access
control — compromising it is equivalent to being invited. Net
surface: equivalent to a static-link model.

## Concerns to surface for external review

### 1. base64url codec duplicated across modules
`utils/crypto/master-key.ts` and `utils/file-sharing/encryption-core.ts`
each define their own base64url encoder. Code duplication.

**Reason for the duplication:** the Collab path was intentionally
dependency-free so the bundle doesn't pull in the ~1000-line
file-sharing encryption module. Acceptable if the two codecs are
tested to agree on the URL-safe character set; they currently are
via their respective round-trip tests.

**Action for reviewer:** sanity-check that both codecs agree on
padding + URL-safe substitutions. If they ever diverge, a cross-
module key import would fail silently.

### 2. Awareness replay — **RESOLVED in v1.1.1 (PR #90)**
A ciphertext `y-awareness` frame replayed by an attacker who saw the
wire would briefly re-surface the frame's cursor state on every peer.

**Mitigation shipped in PR #90:** every outbound `y-awareness` frame
carries a per-peer monotonic counter (`c`). Receivers track the max
seen per peer and drop frames with non-increasing `c`. Back-compat
preserved by accepting frames missing `c` (from v1.1 clients).
Tested via `provider.replay.test.ts` (5 tests) + the integration
harness's 3-peer awareness test.

**Residual concern:** a receiver whose peer drops mid-session and
reconnects with a new PeerState loses its counter history. A
replayed frame from the pre-reconnect period would be accepted
because `awarenessMaxC` is back to 0. Acceptable for v1.1.1 — the
window is bounded by the reconnect latency and the Awareness module
re-broadcasts on heartbeat, so the stale state is corrected within
a second.

### 3. Non-extractable sub-keys
`deriveSubKey` sets the sub-key non-extractable. Callers cannot
export them. Correct for defense-in-depth — a JS memory leak can't
dump the sub-key — but it also means telemetry can't fingerprint
the key (which is fine, we don't want that anyway).

**Action for reviewer:** confirm the policy suits Rapidly's crash-
dump + Sentry posture. If Sentry ever stringifies a `CryptoKey`, it
gets `[object CryptoKey]` which leaks nothing.

### 4. Handshake race under mesh reconnect
PR #79's `addPeer` is idempotent (existing peer is removed +
replaced). If the mesh reconnects mid-edit, the new `addPeer` races
against the in-flight hello+sync. Yjs convergence is eventually-
consistent so no data loss, but the "Securing…" badge might flash.

**Action for reviewer:** verify the `detachersRef` cleanup path in
`useCollabRoom` actually runs on reconnect — if it doesn't, there's
a handler leak. (Local test coverage: `provider.test.ts`'s
idempotence test, but that's the in-process room, not the hook.)

### 5. Room cleanup on tab close
If the host tab closes without clicking "End session", `closeSession`
is not called. The Redis channel TTL (2 h) eventually reaps. Guests
still connected stay connected until the signaling server notices
the host's WebSocket closed.

**Not a v1.1 E2EE concern**, just a lifecycle observation — the E2EE
layer doesn't introduce this, the base session model did.

### 6. No server-side cap on per-peer decrypt failures
A hostile peer could pump garbage frames at us. Our decrypt-null
drop is O(ciphertext length); cheap, but unbounded. A peer sending
100 MB/s of garbage is a DoS vector.

**Mitigation not yet implemented:** rate-limit inbound bytes per
peer in `useCollabRoom`'s transport adapter.

**Action for reviewer:** plausible attack vector or overthinking?
The signaling + WebRTC layer already has its own rate limits; the
Collab layer trusting them is consistent with how Screen/Watch/Call
operate.

## Test coverage summary

| PR | Tests added | Pinned invariant |
|---|---|---|
| #78 | 18 | Round-trip, tamper detect, IV freshness, key separation, encode |
| #79 | 5 | Both-e2ee convergence, mixed → plaintext (before #81), key-mismatch no-crash, status transitions |
| #80 | 9 | Fragment round-trip, leading-#, absent/malformed, missing s, bad key |
| #81 | 1 (rewrote #79's mixed-peer test) | No-downgrade: keyed side never emits plaintext |
| #82 | 7 | Aggregator rules: solo/pending/e2ee/mixed/plaintext |

**Total new tests across v1.1: 40**, exclusive of the 34 Phase E v1
tests already covering the unencrypted path.

## What the author worries about most

In order of decreasing sleep-loss:

1. **The handshake's hidden assumptions.** The settled flag + pending
   queue are new state; the author wrote it in one pass and test-
   covered the happy path well but didn't exhaustively explore
   partial-failure scenarios (A sends hello, dies before sync, B
   stuck in `pending` forever? — the timer-based status in PR #82
   masks this by showing "Securing…" indefinitely).

2. **Browser Web Crypto edge cases.** Firefox's HKDF import has
   historically been strict about extractable flags. Tested on
   Chromium via vitest; should smoke-test real Firefox in staging
   before flipping the default on.

3. **The clipboard path for invite URLs.** PR #80's
   `encodeInviteFragment` → `navigator.clipboard.writeText` is
   twitchy on older mobile Safari. Fallback-render the URL is
   already there (the `{lastInvite}` pill in the host client), but
   the UX of "please copy this manually" is not elegant.

## Explicit asks for the reviewer

1. Decide whether awareness-replay (Concern #2) blocks merge or
   belongs in v1.2.
2. Run the v1.1 stack in **real Firefox and real Safari** before
   flipping the default on — vitest is Chromium-only.
3. Read PR #81's `onHelloReceived` comment twice. If you disagree
   with the no-downgrade stance (i.e., you think a rolling deploy
   requires re-enabling plaintext fallback temporarily), block the
   merge and negotiate the staged rollout in the PR description.

## What this doc is not

- Not a commitment from Rapidly about the strength of v1.1.
- Not a substitute for external security review.
- Not a threat model that covers v1.2 ratchet / post-quantum / MITM
  on the invite URL transport (the user's messenger).

It's a working note the author left for whoever reviews the code
next, written while the design was still fresh.
