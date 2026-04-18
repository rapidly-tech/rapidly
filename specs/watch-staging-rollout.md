# Watch chamber — staging rollout runbook

Phase C v1 (URL-only) is merged. This is the operator playbook for
flipping `FILE_SHARING_WATCH_ENABLED` on staging and running the
two-browser sync validation. Stay next to the Hetzner terminal with
this open.

## Prerequisites
- SSH to the Hetzner staging box.
- Access to the staging frontend build environment.
- Two browsers (Chrome + Firefox, or two Chrome profiles) on the same
  machine or different networks. At least one public video URL to test
  with — a free sample like
  `https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/BigBuckBunny.mp4`.

## 1. Flip the backend flag

```bash
ssh staging
sudo -i
cd /opt/rapidly
# Edit server env file, add or uncomment:
#   RAPIDLY_FILE_SHARING_WATCH_ENABLED=true
docker compose -f docker-compose.staging.yml up -d api
docker compose -f docker-compose.staging.yml logs -f api --tail=50
```

Expect `watch_session_created` events in the log once you run step 4.

**Rollback:** set the var to `false` and `docker compose up -d api`.
Endpoints immediately 404; existing sessions finish their TTL (1 hour)
and self-destruct. The invite-token SET at
`file-sharing:watch:invite:{slug}` is TTL'd and needs no cleanup.

## 2. Frontend already ships Watch UI

The `/watch` and `/watch/[slug]` routes are compiled into every build —
no separate flag flip on the frontend. The Revolver's Watch chamber
already renders as `live`, so once the backend flag is on, the whole
flow works.

If you also want the 6-chamber revolver at `/`, flip
`NEXT_PUBLIC_REVOLVER_LANDING=true` per the Screen runbook.

## 3. Smoke-test the API from your laptop

```bash
export STAGING=https://staging.rapidly.tech

# Create a watch session (URL-only v1).
curl -sS -X POST "$STAGING/api/v1/watch/session" \
  -H 'Content-Type: application/json' \
  -d '{"title":"staging smoke","max_viewers":3,
       "source_url":"https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/BigBuckBunny.mp4"}' | jq .
```

Expected: 200 with `short_slug`, `long_slug`, `secret`, `invite_template`.
If you get a 404 the flag is off (or the router is not mounted — check
`/api/docs`). If you get a 422 your payload is malformed — most likely
`source_url` lacks a scheme or uses something non-http(s).

**Defense-in-depth check:** attempt to create a session with a
dangerous scheme. All three of these should return **422**:

```bash
for url in 'javascript:alert(1)' 'data:text/html,<x>' 'ftp://example.com/v.mp4'; do
  echo -n "$url → "
  curl -sS -o /dev/null -w "%{http_code}\n" -X POST "$STAGING/api/v1/watch/session" \
    -H 'Content-Type: application/json' -d "{\"source_url\":\"$url\"}"
done
```

This confirms `CreateWatchSessionRequest._scheme_must_be_http` is
rejecting crafted URLs at the boundary, not relying on client-side
sanitising alone.

## 4. Two-browser sync smoke

1. **Browser A (host):** open `https://<staging>/watch`.
   - Paste a public video URL into the input.
   - Click **Start watching**. Video appears with native controls.
2. **Browser A (host):** click **Copy invite link**. Clipboard now
   holds `https://<staging>/watch/{slug}?t={token}`.
3. **Browser B (guest):** paste the invite URL, load, click **Join now**.
   - Expected within ~5s: guest video starts playing at the host's
     current position, in sync. No controls visible — the guest is a
     follower, not a driver.
4. **Host → Guest sync invariants to verify by hand:**
   - Host pauses → guest pauses within ~100 ms.
   - Host seeks forward 60s → guest seeks within ~200 ms.
   - Host lets video play uninterrupted → guest drifts **<100 ms**
     after 5 min of playback (open browser devtools; compare
     `video.currentTime` on both).
5. **Host ends session:**
   - Click **End session** on the host. Guest transitions to
     "Session ended".
6. **Follow-up:** hit `GET /api/v1/watch/session/{slug}`. Expected:
   404 (session destroyed, invites revoked).

## 5. Drift kill criterion

The spec says "if Watch sync consistently drifts >500 ms on same-LAN
connections across the three most common browsers, rethink the
architecture before shipping." Test this explicitly:

- Same-LAN: host in Chrome, guest in Firefox on the same laptop.
  Target drift <100 ms after 10 min of continuous playback.
- Cross-NAT (one browser on cellular tether): target drift <300 ms
  after 10 min.

If either test blows past the kill criterion, **do not flip production**.
File an issue with the drift measurements + network conditions.

## 6. Rollback

Flag flip back to `false` → endpoints 404 immediately. Existing
sessions keep running until their TTL expires (1 hour). No migrations,
no Redis state to clean.

## 7. Observations worth capturing

- P95 time-to-first-frame: guest click Join → video renders first
  frame.
- Percentage of sessions that correct drift via rate-nudge vs fall back
  to visible seek.
- Any `ready` messages that don't eventually lead to playback (guest
  stuck buffering).
- Any crashes or console errors in either browser.

Stash these on the same observability surface as the Screen rollout so
the next chamber (Call / Collab) has a baseline.
