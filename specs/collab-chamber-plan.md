# Collab chamber — phase plan (kickoff)

**Phase:** E, last chamber of the v1 revolver.
**Status:** Planning.
**Depends on:** Phase B–D (Screen / Watch / Call) all merged. The
signaling server + invite-token model + auth-validator registry +
`PeerDataConnection` are exactly what we need — no new transport
primitives required.

## Goal

"Realtime docs and whiteboards, locally-first." A host opens a
collaborative document (text or canvas), mints an invite link,
participants join and see each other's edits appear in real time with
no server-side conflict resolution. Local-first, end-to-end
encrypted, bounded at ~8 participants per room for v1.

## What's genuinely new

Unlike Screen (one broadcaster), Watch (host clock + media playback),
and Call (symmetric A/V mesh), Collab is the first chamber where **the
participants co-author persistent state**. That means we need:

1. A CRDT (Conflict-free Replicated Data Type) so every participant
   converges to the same document regardless of edit order.
2. A persistence strategy — the document has to survive every
   participant closing their tab. "Local-first" means at least one
   participant holds the ground truth on disk; on first boot of a new
   session, any peer's copy suffices.
3. A sync model over the existing `PeerDataConnection`: periodic
   update packets + on-demand state syncs when a new peer joins.

## What reuses Phase B–D wholesale

- Session CRUD, invite tokens, auth validators — copy from the Call
  chamber. `session_kind="collab"`, `max_participants` cap up to 8.
- Feature-flag + revolver chamber pattern — identical.
- `PeerDataConnection.send(msg)` over the existing DC for CRDT update
  packets. Binary framing (4-byte header len, length-prefixed binary
  payload) already ships in the transport.
- Mesh coordinator from PR 14 — for the N-way peer-connection
  management.

## Gold-standard references

| Ref | What we take |
|---|---|
| **Yjs** | The CRDT itself. Y.Doc with Y.Text / Y.Map / Y.Array covers everything we need for v1. Well-tested, small runtime (~40kb gzipped), MIT-licensed. |
| **y-webrtc** | Their provider shape — `Awareness` for presence, `sync` step 1/step 2 handshake, sparse update broadcast. We don't use y-webrtc directly (it bundles its own signaling); we write a Rapidly-native provider that pumps Yjs updates through our `PeerDataConnection`. |
| **Automerge** | Considered and rejected — heavier runtime, larger binary updates, slower merge on our likely use cases (text + canvas). Revisit if a v2 needs richer history. |

## PR-by-PR breakdown

| PR | Title | Scope |
|---|---|---|
| **16** | Collab backend | Mirror of PR 13 (Call backend). `session_kind="collab"`, `FILE_SHARING_COLLAB_ENABLED`, 4 endpoints, 2 validators, Redis invite tokens. ~1500 LOC + 40 tests. |
| **17** | Yjs provider over PeerDataConnection | The novel piece. `createCollabRoom(roomId, mesh, signaling) → { doc: Y.Doc, awareness: Awareness, close(): void }`. On new peer: sync step 1 (encoded state vector) → step 2 (encoded diff). On every local edit: broadcast the update to all peers. On incoming update: apply. Unit tests with a shared-memory pair of rooms. |
| **18** | Collab UI — `/collab` lobby + `/collab/[slug]` editor with a simple textarea + presence cursors. Feature-flagged; flip chamber to `live`. |
| **19 (optional)** | Whiteboard editor. Canvas-based, uses a Y.Array of stroke objects. Separate PR so PR 18 can ship without it. |

## Session model (backend)

Same as Call but:
```python
collab_kind: str = "text"     # "text" | "canvas"
max_participants: int = 8      # larger ceiling than Call mesh
collab_started_at: str | None = None
```

Larger cap is OK because Yjs is bandwidth-efficient — individual edit
updates are ~30–200 bytes and get compressed. An 8-way mesh handles
this comfortably.

Invite model, feature flag, Redis keys all identical pattern.

## Data flow

```
              signaling
                 ▼
          ┌──────────────┐
          │ PeerData     │ each pair of peers
          │ Connection×N │ has its own DC
          └──────┬───────┘
                 │ JSON updates
                 ▼
          ┌──────────────┐
          │ Yjs Provider │ maintains doc consistency
          └──────┬───────┘
                 ▼
             Y.Doc ─── Y.Text (textarea)
                  └── Y.Array (canvas strokes)
                  └── Awareness (cursors, presence)
```

The provider is a thin layer: listens to DC messages, applies with
`Y.applyUpdate(doc, update)`; subscribes to `doc.on('update', …)` and
broadcasts outbound.

## Persistence strategy

v1: every participant holds the doc in memory. When the last tab
closes, the doc is lost. That's deliberately tight — **Collab v1 is
ephemeral collab**, same promise as Screen and Call.

v2 (if demand surfaces): offer a "save snapshot" button that downloads
the encoded state. A later session can rehydrate by uploading.

## What's out of scope for Phase E v1

- No server-side persistence of document state (it's an ephemeral
  peer-to-peer product).
- No rich-text formatting (plain text only in the textarea variant).
- No version history / time-travel.
- No moderation controls (host-only edit locks).
- No federation with external docs (Notion, Google Docs, etc.).
- No offline-first sync — participants must be simultaneously online
  to co-edit. Persistence layer could relax this in v2.

## Risk

Medium-low. Yjs is battle-tested, the sync protocol is well-documented,
and our transport layer gives us exactly the primitive shape Yjs's
provider API expects. The main unknowns:

- **Presence flicker** on slow networks — awareness updates arriving
  seconds apart can make cursors ghost. Y's Awareness module handles
  this well; we just need to wire the ping interval.
- **State sync for late joiners on large docs** — encoded state vectors
  can get big (~KB for a 10-min editing session). Our DC fragmentation
  already handles >256KB messages, so this is "slow to bootstrap" not
  "broken".

## Kill criterion

If a 4-participant text edit session produces diverging documents
within 30 minutes of continuous editing across Chrome + Firefox, stop
and audit the provider. Yjs's own test suite proves CRDT correctness;
the only way to observe divergence is a provider bug.

## First commit target

PR 16 is a clone of PR 13 (Call backend). Estimated ~1500 LOC + 40
tests. If the pattern continues to hold, PR 16 should take less time
than PR 13, and PR 17 (the Yjs provider) is the interesting commit.
