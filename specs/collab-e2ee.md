# Collab chamber — end-to-end encryption (v1.1 spec)

**Status:** planning. Not implemented — this doc pins the design so
the v1.1 PR can land without re-deriving the cryptography decisions.

## Why

Phase E v1 ships the Collab chamber with **DTLS-only** encryption.
That means:

- No Rapidly server ever sees the plaintext doc body (DTLS rides end
  to end between browsers).
- Every peer inside a session can read every other peer's edits. A
  hostile invitee could silently mirror the doc.

The second point is acceptable for v1 because invite tokens are the
access control — if you send a link to the wrong person, they can
read it, same as sending a Google Doc link. But the clean-room
policy ([feedback_clean_room_policy.md]) says _"All P2P sessions
E2E-encrypted at app layer"_, and v1 only satisfies the letter (DTLS
is "at transport", not "at app"). v1.1 closes that gap.

## Threat model

| Adversary | v1 posture | v1.1 target |
|---|---|---|
| Passive network eavesdropper | ✅ DTLS | ✅ DTLS + app-layer AES-GCM |
| Rapidly server operator | ✅ Cannot decrypt DTLS | ✅ Doc content never touches the server |
| Malicious invitee in-session | ❌ Reads everything | ❌ Still reads (same invite-token trust model) |
| Link-forwarding to third party | ❌ Third party reads | ❌ Still reads unless host rotates key |

The v1.1 work is about the first two rows. The third row is the
"invite is capability" model, which does not change; out-of-band
trust establishment (e.g., signed invites) is a later v1.2 item.

## Design

### 1. Room master key

The host generates a fresh 256-bit AES-GCM master key on session
create. It is **never** sent to the Rapidly server.

```typescript
const masterKey = await generateMasterKey() // existing: utils/file-sharing/encryption.ts
```

The master key flows to every invitee via the invite **URL fragment**:

```
https://<origin>/collab/<slug>?t=<token>#k=<base64-master-key>
```

The fragment is not transmitted to the server in the HTTP request.
This matches the file-sharing chamber's pattern and reuses the same
`generateMasterKey` + `exportMasterKey` primitives.

### 2. Per-update encryption

The Yjs provider's wire format currently ships three message types
(`y-sync-1`, `y-sync-2`, `y-awareness`) carrying a `bytes: Uint8Array`
payload. v1.1 adds an encryption envelope around the bytes:

```typescript
// Before:
send({ t: 'y-sync-2', bytes: update })

// After:
const { iv, ciphertext } = await encrypt(masterKey, update)
send({ t: 'y-sync-2', iv, bytes: ciphertext })
```

AES-GCM with a 12-byte IV per message. The IV is generated fresh per
send (`crypto.getRandomValues`). AES-GCM's authentication tag is
appended to the ciphertext, giving tamper-detection for free.

### 3. Key derivation

We do not encrypt with the master key directly. HKDF splits it into
three per-session sub-keys so the same master can safely encrypt
many Yjs updates without approaching the GCM birthday bound (2^32
messages per key):

- `sync-key` — used for `y-sync-1` / `y-sync-2`.
- `awareness-key` — used for `y-awareness`.
- `reserved` — spare slot for a future ratchet.

HKDF infos: `collab:sync:v1`, `collab:awareness:v1`,
`collab:reserved:v1`. Binding the chamber name + version prevents
cross-chamber reuse attacks if the same master is ever (wrongly)
reused elsewhere.

### 4. Key rotation on peer leave

A room's master key is static for the session's lifetime. Removing
a peer from the mesh does _not_ strip their ability to decrypt past
traffic (they already have the master). **This is deliberate** — v1.1
matches v1's trust model where invites are permanent capabilities.

If a future PR needs forward secrecy on leave, a ratchet
(Double-Ratchet or similar) replaces the static HKDF scheme. Tracked
in the `reserved` info slot above.

### 5. Signaling-layer implications

None. Signaling already relies on the invite token in the URL path
(`?t=`) and does not see the fragment (`#k=`). The server cannot
distinguish a v1 client from a v1.1 client from the signaling layer.

## Client/backend compatibility

- **Backend:** no changes. The invite-token model, channel state, and
  validator registry are all transport-level and agnostic to payload
  encryption.
- **Client:** v1.1 clients must handshake a small `y-sync-hello`
  message that advertises `{"e": "v1"}`. If either side does not
  present this, both fall back to plaintext (v1 behaviour). This
  keeps a rolling deployment safe: staging can run v1.1 clients while
  a single outdated tab on the network stays functional.

## Implementation PR shape

1. **PR A — primitives**: promote `utils/file-sharing/encryption.ts`
   to `utils/crypto/aes-gcm.ts` (or re-export from a shared path) so
   the Collab provider can import without pulling the whole
   file-sharing module.
2. **PR B — envelope**: add `{iv, bytes}` framing + `y-sync-hello`
   handshake to the Collab provider. Feature-gated behind
   `NEXT_PUBLIC_COLLAB_E2EE=true` for staging rollout.
3. **PR C — URL fragment**: host puts master key in `#k=...`, guest
   parses it on page load. Gracefully fail to v1 plaintext when
   fragment missing.
4. **PR D — enable + remove fallback**: once all reachable clients
   are v1.1, drop the plaintext fallback. Flag flipped to `true` by
   default.

## Testing

- Reuse the existing `utils/collab/provider.test.ts` shared-memory
  harness. Add a second suite where both transports wrap messages
  with `encrypt` / `decrypt` from `encryption.ts`. Convergence tests
  continue to pass unchanged.
- Add a test where one side mutates a byte of ciphertext in transit
  — AES-GCM's auth tag must cause `decrypt` to throw, and the
  receiving room must log-and-drop rather than crashing.

## Kill criterion

If v1.1 measurably slows typical text editing (>50 ms added latency
per keystroke on a mid-spec laptop), revert and revisit the HKDF
cadence. AES-GCM on `Uint8Array` inputs should be low-microsecond on
modern browsers; this is an overcautious guardrail.

## Gold-standard reference

- **libsignal protocol**: considered for forward-secrecy ratchet;
  not used because v1.1 sticks with the static HKDF scheme. Ratchet
  migration is tracked as v1.2 if the need surfaces.
- **matrix-js-sdk (Megolm)**: similar design space (group session
  ratchet). Reviewed for the "fan-out key rotation on membership
  change" concept — intentionally _not_ adopted for v1.1.
- **Rapidly's own file-sharing encryption** (`utils/file-sharing/encryption.ts`):
  master-key-in-URL-fragment + HKDF derivation is the same pattern
  we ship today for files. v1.1 is "apply the existing pattern to
  the Collab wire, not the file chunk".
