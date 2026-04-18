# Screen chamber — staging rollout runbook

Phase B is merged. This doc is the operator playbook for flipping the two flags and validating the stack end-to-end on Hetzner staging. Keep this next to the Hetzner terminal when you roll.

## Prerequisites
- SSH to the Hetzner staging box.
- Access to the staging frontend build environment (so you can set `NEXT_PUBLIC_REVOLVER_LANDING`).
- Two browsers (Chrome + Firefox, or two Chrome profiles) on the same machine or different networks.

## 1. Flip the backend flag

```bash
# On the Hetzner staging host
ssh staging
sudo -i
cd /opt/rapidly
# Edit the server env file, find or add:
#   RAPIDLY_FILE_SHARING_SCREEN_ENABLED=true
# Then restart only the API container to pick up the change:
docker compose -f docker-compose.staging.yml up -d api
docker compose -f docker-compose.staging.yml logs -f api --tail=50
```

The API should log `[INFO] screen_session_created` events once you run step 4. If you see `AttributeError: ... FILE_SHARING_SCREEN_ENABLED` on boot, the env var did not reach the container — check `docker compose config | grep SCREEN`.

**Rollback:** unset the var (or set to `false`) and `docker compose up -d api`. The endpoints immediately 404; no state to clean up because `session_kind="screen"` channels only exist when the flag is on.

## 2. Flip the frontend flag

```bash
# On whichever system builds the staging frontend (Vercel / Cloudflare Pages / a Hetzner build container):
# Set NEXT_PUBLIC_REVOLVER_LANDING=true in the environment
# Trigger a new build + deploy.
```

The revolver replaces the current landing once the new build ships. **This flag is build-time** — unsetting it requires another build, not a live reload. Leave the existing landing untouched in the meantime: the flag gates at the component boundary inside `app/(main)/(website)/(landing)/page.tsx`.

## 3. Smoke-test the API from your laptop

```bash
export STAGING=https://staging.rapidly.tech   # adjust to your staging domain

# Create a screen session. Response should include short_slug + secret.
curl -sS -X POST "$STAGING/api/v1/screen/session" \
  -H 'Content-Type: application/json' \
  -d '{"title":"staging smoke","max_viewers":3}' | jq .

# The four endpoints are exhaustively smoke-tested by the vitest suite
# (tests/sharing/screen/test_api.py, 12 cases). If this one POST returns
# 200 with a slug + secret, the rest are almost certainly fine.
```

Expected failure modes if something is wrong:
| Symptom | Root cause |
|---|---|
| `404 Not Found` | Flag is off, or the screen router is not mounted. Check `/api/v1/screen/session` in the OpenAPI doc at `/api/docs`. |
| `500 Internal Server Error` with Redis key error | `FILE_SHARING_SIGNALING_BACKEND` is `redis` but Redis is unreachable. See `specs/redis-signaling-transport.md`. |
| `422 max_viewers` on a ≤10 payload | Schema validator changed — someone broke the request model. |

## 4. Two-browser screen-share smoke

1. **Browser A (host)**: open `https://<staging>/screen`.
   - Click "Start sharing".
   - Pick a window (for least drama — whole-screen works but can recurse into the browser tab running the preview).
   - Expected: local preview video, "0 viewers connected" panel.
2. **Browser A (host)**: click "Copy invite link". The clipboard now holds `https://<staging>/screen/{slug}?t={token}`.
3. **Browser B (guest)**: paste the invite URL and load it.
   - Expected: "Screen share" landing with a "Join now" button.
   - Click "Join now".
   - Expected within ~5s: remote video plays, "Connected peer-to-peer" caption visible.
4. **Browser A (host)**: viewer count increments to 1.
5. **Browser A (host)**: click "Stop sharing".
   - Expected: guest transitions to "Session ended" view.
6. **Browser B (guest)**: reload the URL. Expected: 404 / "Session not found" (the channel was destroyed by the close).

## 5. TURN fallback sanity check

Repeat step 4 with Browser B connected through a VPN (or a phone on cellular data) so the two browsers are on different NATs. Expected: WebRTC succeeds via TURN relay inside ~15s. If it fails:
- `chrome://webrtc-internals` on both browsers shows which candidate pairs were tried.
- The `coturn` container logs on the Hetzner box should show the TURN allocation.

## 6. Rollback

Backend flag flip back to `false` → endpoints 404, existing sessions still reachable until their TTL expires (1 hour for screen). No database migration, no Redis state to clean. The invite-token SET at `file-sharing:screen:invite:{slug}` is TTL'd and will self-destruct.

Frontend: redeploy without the `NEXT_PUBLIC_REVOLVER_LANDING` env var. The code path without the flag is the pre-existing landing — zero risk of a "new-landing only" bug affecting users.

## 7. Post-rollout observations to capture

- P95 time-to-first-frame from "Join now" click → remote video appears (target: <3s on same-network, <8s on TURN).
- Signaling WebSocket connection success rate (dashboard or manual count).
- Any `screen_session_created` / `screen_session_closed` events missing from the log — they're the best leading indicator of a signaling bug.

Stash these in whatever observability surface you use so the next chamber launch (Watch) has a baseline to beat.
