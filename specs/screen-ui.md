# Spec: Screen UI + revolver landing (PR 7)

**Phase:** B, PR 7 (third Phase B PR; depends on #48 + #49)
**Status:** Draft → Implemented in this commit
**Scope:** Minimum viable Screen UI (host + guest pages) + the 6-chamber revolver landing at `/`.

## Goal

Deliver the whole user-visible slice of Phase B:

1. Wire the PR 5 backend + PR 6 media-track surface into two usable pages so a host can share their screen and a guest can watch.
2. Replace the current root landing with the 6-chamber revolver UI — Files, Secret, Screen, Watch, Call, Collab — where each chamber is a clickable segment. Live chambers link to their routes; not-yet-shipped chambers render a "coming soon" state.

**Non-goals:**
- No host-side guest list / kicking.
- No chat / reactions.
- No recording.
- No revolver rotation animation on chamber activation — a single on-hover scale is enough for v1.
- No accessibility round beyond keyboard-reachable chamber buttons — a dedicated pass follows the vertical slice.

## Routes

| Path | Owner | Behaviour |
|---|---|---|
| `/screen` | Host | Page with a "Start sharing" button. On click: `getDisplayMedia()`, `POST /api/v1/screen/session`, connect signaling as host, `addTrack`, render local preview + invite URL. |
| `/screen/[slug]` | Guest | Reads `?t=<token>` from URL. `GET /api/v1/screen/session/{slug}` for metadata. Connect signaling as guest, `onTrack` attaches remote stream to `<video>`. |

Both pages live under `app/(main)` so the existing top bar / auth surfaces remain. Pages fail closed when `FILE_SHARING_SCREEN_ENABLED=False` (the backend 404s; the page renders a friendly "not available" view).

## Components + hooks

```
hooks/screen/useScreenHost.ts           — orchestrates host flow
hooks/screen/useScreenGuest.ts          — orchestrates guest flow
utils/screen/api.ts                     — fetch wrappers for the 4 backend endpoints
components/Screen/ScreenHostClient.tsx
components/Screen/ScreenGuestClient.tsx
components/Revolver/Revolver.tsx        — SVG-based 6-chamber radial UI
components/Revolver/chambers.ts         — chamber registry (id, label, icon, href, status)
app/(main)/screen/page.tsx
app/(main)/screen/[slug]/page.tsx
app/(main)/(website)/(landing)/revolver/page.tsx  — preview route for the revolver
```

The root landing swap (`/` → revolver) is staged behind a small feature toggle so we can validate the revolver in isolation before flipping the primary CTA. The hooks return a `{ status, error, startSharing, stop, ... }` shape so the component layer is dumb — just renders based on status.

## Revolver design

Six chambers arranged in a hexagonal ring. Each chamber is a clickable segment with: icon, label, status pill (`live` / `soon`).

| Chamber | Icon | Route | Status |
|---|---|---|---|
| Files | `FileIcon` | `/dashboard` (existing) | live |
| Secret | `LockIcon` | `/secret` (existing) | live |
| Screen | `MonitorIcon` | `/screen` (new in this PR) | live |
| Watch | `EyeIcon` | `/watch` | soon |
| Call | `PhoneIcon` | `/call` | soon |
| Collab | `UsersIcon` | `/collab` | soon |

Geometry: six chambers at 60° spacing, radius sized to fit the viewport with a central "Rapidly" logo. Built with a single SVG + CSS transforms so there are no layout dependencies that break at odd viewport sizes. Chambers with `status: "soon"` render a subtle disabled treatment but still receive focus for keyboard users who want to tab through to learn what's coming.

The hooks return a `{ status, error, startSharing, stop, ... }` shape so the component layer is dumb — just renders based on status.

## Invite-token UX

Host UI shows the `invite_template` returned by `POST /session` and a "Copy invite" button that substitutes a freshly-minted token each time (clicking Copy = `POST /session/{slug}/invite` → replace `{token}` in the template → copy to clipboard). This lets the host distribute per-guest links without exposing the channel secret.

## Signaling wire protocol

No new messages. Host identifies as `{ role: "host", secret }` and guest as `{ role: "guest", token }`, both on the existing first-message auth path registered in PR 5. Signaling client is the same `SignalingClient` used by file-sharing — zero changes.

## Failure modes handled

| Case | Treatment |
|---|---|
| `getDisplayMedia` rejected (user clicks cancel) | Status → `idle`, surface "Share cancelled" toast. |
| `POST /session` returns 404 | Feature disabled → show "Screen sharing is not enabled on this deployment". |
| Guest page: `?t=<token>` missing | Show "Invite link is invalid" + CTA to go home. |
| Guest auth rejected (signaling close 4003) | "Invite expired or session ended". |
| Host tab closed | `close()` on `PeerDataConnection` stops local tracks + fires onclose on guest side; guest shows "Host left". |

## Tests

Unit-level only for PR 7:
1. `utils/screen/api.ts` — URL construction + status-code → Error mapping.
2. `useScreenHost` state machine — the status transitions (`idle → requesting → active → closed`) with mocked fetch + getDisplayMedia.
3. `useScreenGuest` state machine — (`joining → active → ended`) with mocked fetch + signaling.

Full two-browser end-to-end is deferred to the post-merge staging smoke.

## Risk

Medium: this is the first chunk of client code that actually touches live WebRTC. The underlying primitives (PR 6) are unit-tested, but the integration has surface area. Mitigations:
- Feature flag stays off until staging validation.
- No file-sharing code paths are touched.
- Pages render a "not available" state when the flag is off so accidental traffic does nothing.

## Kill criterion

If file-sharing UI regresses in manual QA or CI, revert. The new pages import nothing from file-sharing hooks; everything they need is freshly imported, so deleting the PR 7 directories is a clean undo.
