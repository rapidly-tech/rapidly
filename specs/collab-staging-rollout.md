# Collab chamber — staging rollout runbook

Phase E v1 (realtime doc + whiteboard, up to 4 peers) is merged.
Operator playbook for flipping `FILE_SHARING_COLLAB_ENABLED` on
Hetzner staging and running the two-browser Collab validation.

## Prerequisites

- SSH to the staging box. Hostname + SSH host alias + compose-file
  path live in an uncommitted operator-local env file (same one
  `dev/preflight-collab-staging` reads):

  ```bash
  # ~/.rapidly/staging.env (not committed; chmod 600)
  STAGING_SSH_HOST=<ssh-config-alias>
  STAGING_HTTP_URL=https://<staging-hostname>
  STAGING_COMPOSE_FILE=<path-to-compose-file>
  ```
  Source it in the shell you're running the commands from:
  `source ~/.rapidly/staging.env`.
- Two browsers on separate machines, or two profiles on one box. Any
  modern Chrome / Firefox / Safari works — no camera or mic needed
  (this chamber is text + canvas, not A/V).
- Both participants on **HTTPS**. Not strictly required by the spec
  (no `getUserMedia`) but the signaling server's CSP + WebRTC DTLS
  still want a secure origin for cross-browser reliability.

## 1. Flip the backend flag

```bash
ssh "$STAGING_SSH_HOST"
sudo -i
cd /opt/rapidly
# Edit the server env file, add / uncomment:
#   RAPIDLY_FILE_SHARING_COLLAB_ENABLED=true
docker compose -f "$STAGING_COMPOSE_FILE" up -d api
docker compose -f "$STAGING_COMPOSE_FILE" logs -f api --tail=50
```

Expect `collab_session_created` log entries once step 4 runs.

**Rollback:** unset the var (or set to `false`) and
`docker compose up -d api`. Endpoints immediately 404; existing
sessions expire via TTL (2 h for Collab — longer than Call because
doc sessions tend to run longer) with no migration.

## 2. Frontend already ships Collab UI

`/collab` and `/collab/[slug]` are in every build. The Revolver's
`collab` chamber is `live` on main once the #71→#72→#73(→#74) stack
merges. No separate frontend flag — once the backend is enabled the
pages just work.

## 3. API smoke

```bash
export STAGING="$STAGING_HTTP_URL"

curl -sS -X POST "$STAGING/api/v1/collab/session" \
  -H 'Content-Type: application/json' \
  -d '{"title":"smoke","max_participants":4,"kind":"text"}' | jq .
```

Expected: 200 with `short_slug`, `long_slug`, `secret`, `invite_template`.
404 means the flag is off, 422 means the body is invalid
(`max_participants` ∈ [2, 8], `kind` ∈ {`text`, `canvas`}).

Schema-rejection checks (defense-in-depth — mirrors Call's §3):

```bash
curl -sS -o /dev/null -w "over-cap: %{http_code}\n" \
  -X POST "$STAGING/api/v1/collab/session" \
  -H 'Content-Type: application/json' -d '{"max_participants":9}'
# Expect: 422

curl -sS -o /dev/null -w "under-cap: %{http_code}\n" \
  -X POST "$STAGING/api/v1/collab/session" \
  -H 'Content-Type: application/json' -d '{"max_participants":1}'
# Expect: 422

curl -sS -o /dev/null -w "bad-kind: %{http_code}\n" \
  -X POST "$STAGING/api/v1/collab/session" \
  -H 'Content-Type: application/json' -d '{"kind":"spreadsheet"}'
# Expect: 422
```

Cross-chamber invariant check (mint should refuse a non-collab slug):

```bash
# Create a Call session and try to mint a Collab invite against it.
CALL=$(curl -sS -X POST "$STAGING/api/v1/call/session" \
  -H 'Content-Type: application/json' \
  -d '{"max_participants":2,"mode":"audio_video"}')
CALL_SLUG=$(echo "$CALL" | jq -r .short_slug)
CALL_SECRET=$(echo "$CALL" | jq -r .secret)

curl -sS -o /dev/null -w "cross-chamber: %{http_code}\n" \
  -X POST "$STAGING/api/v1/collab/session/$CALL_SLUG/invite" \
  -H 'Content-Type: application/json' \
  -d "{\"secret\":\"$CALL_SECRET\"}"
# Expect: 404 — Collab refuses to mint invites on Call slugs.
```

## 4. Two-browser Collab smoke

1. **Browser A (host):** open `https://<staging>/collab`. Pick
   **Document**. Click **Start session**. Editor appears with an
   empty textarea and the presence strip showing only "You (host)".
2. **Browser A:** click **Copy invite**. Clipboard holds
   `https://<staging>/collab/{slug}?t={token}`.
3. **Browser B (guest):** paste the invite URL, load. Within ~5s the
   guest auto-joins and sees the editor. Presence strip shows 2 pills
   (self + host).
4. **Sanity invariants (text mode):**
   - Type "hello" on A. B sees "hello" within ~500 ms.
   - Type in the middle of a word on B. A's cursor position does not
     jump; B's text arrives intact.
   - Close A's tab. B's editor keeps its current text (local-first)
     but the presence pill for A disappears.
5. **Whiteboard mode:** repeat steps 1–3 but pick **Whiteboard** on
   host. Each participant draws a stroke; both canvases converge as
   each pointer-up fires. "Clear" on either side clears both canvases
   within one round-trip.
6. **Cross-NAT smoke:** B on cellular tether or a VPN. Target: editor
   syncs within ~15 s via Rapidly-hosted TURN. `chrome://webrtc-internals`
   on both sides shows candidate-pair selection when needed.

## 5. Kill criterion

v1 caps at 4 participants. If a 4-way text session diverges (two
peers see different text after 30 min of continuous editing), pause
the rollout and audit the Yjs provider in `utils/collab/provider.ts`
— Yjs itself is proved convergent, so any observed divergence is a
provider-integration bug.

Likewise for whiteboard: if a stroke pushed on one peer fails to
appear on another within 3 s on LAN, audit the Y.Array binding in
`components/Collab/CollabCanvas.tsx`.

## 6. What v1 does NOT do

- **No server-side persistence.** Document state lives only in the
  connected tabs. When the last tab closes, the document is gone.
  This is deliberate, same promise as Screen / Call.
- **No save-to-file.** A future PR may add "download as .md" /
  "download as .png" based on customer signal.
- **No rich text.** Plain text only — bold, lists, headings are not
  wired to the CRDT and would be lost on first edit.
- **No offline edit + resync.** All peers must be simultaneously
  online to merge edits. Offline-first requires a persistence layer.
- **No E2E encryption of the doc body.** Traffic rides DTLS via
  WebRTC (so no Rapidly server sees it), but two hostile peers in the
  same session can read each other's text. Invite tokens keep hostile
  peers out for v1.
- **No moderation / host lock.** Any connected peer can edit and
  clear the canvas.

## 7. Rollback

Flag back to `false` → endpoints 404 immediately. Existing sessions
TTL-expire (2 h). No database migrations, no Redis cleanup.

## 8. Observations worth capturing

- P95 time from **Start session** click → editor mounted.
- P95 time from local edit → remote tab showing the edit (target: <500
  ms on LAN, <2 s on cross-NAT with TURN).
- Percentage of sessions that use direct ICE vs fall to TURN relay.
- Whiteboard stroke rate: average pts per stroke; max concurrent
  drawers; peak Y.Array size mid-session.
- Awareness flicker incidence on slow networks — if cursors drop out
  and return more than once per minute, tune the awareness heartbeat.

Stash these alongside the Screen / Watch / Call metrics. Collab is
the last chamber of v1; after this the revolver is full.
