# Call chamber — staging rollout runbook

Phase D v1 (1:1 calls) is merged. Operator playbook for flipping
`FILE_SHARING_CALL_ENABLED` on Hetzner staging and running the
two-browser call validation.

## Prerequisites
- SSH to the Hetzner staging box.
- Two browsers with different cameras/mics available (two laptops, or
  two tabs on the same laptop with separate virtual devices). Chrome +
  Firefox is the easiest.
- Both participants on **HTTPS** — `getUserMedia` is blocked on
  insecure origins. Staging's TLS cert must be valid.

## 1. Flip the backend flag

```bash
ssh staging
sudo -i
cd /opt/rapidly
# Edit the server env file, add / uncomment:
#   RAPIDLY_FILE_SHARING_CALL_ENABLED=true
docker compose -f docker-compose.staging.yml up -d api
docker compose -f docker-compose.staging.yml logs -f api --tail=50
```

Expect `call_session_created` log entries once step 4 runs.

**Rollback:** unset the var (or set to `false`) and `docker compose up
-d api`. Endpoints immediately 404; existing sessions expire via TTL
(1 hour) with no migration.

## 2. Frontend already ships Call UI

`/call` and `/call/[slug]` are in every build. The Revolver's `call`
chamber is `live` on main. No separate frontend flag. Once the
backend is enabled the pages just work.

## 3. API smoke

```bash
export STAGING=https://staging.rapidly.tech

curl -sS -X POST "$STAGING/api/v1/call/session" \
  -H 'Content-Type: application/json' \
  -d '{"title":"smoke","max_participants":2,"mode":"audio_video"}' | jq .
```

Expected: 200 with `short_slug`, `long_slug`, `secret`, `invite_template`.
404 means flag is off, 422 means the body is invalid (check
`max_participants` ∈ [2, 4] and `mode` ∈ {`audio_only`, `audio_video`}).

Schema-rejection check (defense-in-depth):

```bash
curl -sS -o /dev/null -w "over-cap: %{http_code}\n" -X POST "$STAGING/api/v1/call/session" \
  -H 'Content-Type: application/json' -d '{"max_participants":5}'
# Expect: 422

curl -sS -o /dev/null -w "bad-mode: %{http_code}\n" -X POST "$STAGING/api/v1/call/session" \
  -H 'Content-Type: application/json' -d '{"mode":"video_only"}'
# Expect: 422
```

## 4. Two-browser call smoke

1. **Browser A (host):** open `https://<staging>/call`. Click
   **Start call**. Grant camera + mic when prompted. Local tile
   appears, placeholder "Waiting for someone to join…" on the right.
2. **Browser A:** click **Copy invite**. Clipboard holds
   `https://<staging>/call/{slug}?t={token}`.
3. **Browser B (guest):** paste the invite URL, load. Click **Join now**.
   Grant camera + mic. Within ~5s both tiles should show live video.
4. **Sanity invariants:**
   - Both participants can see each other and hear each other.
   - **Mute** on host: audio stops on guest's speaker.
   - **Camera off** on host: host's tile shows "Camera off" on guest's
     screen.
   - **Leave** on host: guest sees "Call ended" within a few seconds.
5. **Cross-NAT smoke:** repeat with Browser B on cellular tether or
   a VPN so the two peers are on different networks. Target: call
   connects within ~15s via Rapidly-hosted TURN. `chrome://webrtc-internals`
   on both sides shows candidate-pair selection if you need to debug.

## 5. Kill criterion

v1 is 1:1. If audio/video consistently shows >300 ms glass-to-glass
latency on same-LAN, or fails to connect on 30%+ of cross-NAT tests,
pause the rollout and debug TURN / ICE config before enabling
production traffic.

## 6. What v1 does NOT do

- **No 3+ participants.** Third guest can reach the signaling server
  but won't learn about the other peers (no roster broadcast yet).
  The UI caps `max_participants=2`; a larger value would be accepted
  by the backend schema but the mesh won't fan out. Tracked as a
  follow-up.
- **No SFU.** Pure mesh. Fine at 2, planned to stay pure mesh up to 4.
- **No recording.**
- **No screen-within-call.** Use Screen separately for now.

## 7. Rollback

Flag back to `false` → endpoints 404 immediately. Existing sessions
TTL-expire. No database migrations, no Redis cleanup.

## 8. Observations worth capturing

- P95 time from **Join now** click → remote track attached to `<video>`.
- Percentage of sessions that use direct ICE vs fall to TURN relay.
- Any `getUserMedia` permission denials (surface via logs if you add
  client-side telemetry; currently silent).

Stash these alongside the Screen + Watch metrics so Collab's rollout
has three chambers of baseline data to beat.
