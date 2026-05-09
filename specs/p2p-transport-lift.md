# Spec: Lift P2P transport out of `utils/file-sharing/`

**Phase:** A, PR 2
**Status:** Draft → Implemented in this commit
**Related PRs:** PR 0 (verify.sh), PR 1 (`session_kind`)

## Goal

Move the three transport classes (`PeerDataConnection`, `SignalingClient`, `WebSocketRelay`) from `clients/apps/web/src/utils/file-sharing/` to `clients/apps/web/src/utils/p2p/`, so file-sharing becomes one *consumer* of a reusable P2P transport rather than the owner.

**No behaviour change.** File-sharing uploads and downloads must work identically to before this PR.

## Non-goals

- No feature additions. No new chambers.
- No modifications to wire protocol, SDP handling, data-channel framing, fragment reassembly, relay throughput caps.
- No change to the signaling server, COTURN config, or backend routes.
- No code removal from `utils/file-sharing/` beyond the three moved files and the three transport constants.

## Design

### 1. New folder: `utils/p2p/`

Contents after this PR:
```
utils/p2p/
  constants.ts   — BUFFER_THRESHOLD, MAX_FRAME_SIZE, MAX_HEADER_SIZE
  logger.ts      — generic dev-only logger (same body as file-sharing/logger.ts)
  peer-connection.ts   — moved via `git mv`
  signaling.ts         — moved via `git mv`, constructor change (see §3)
  ws-relay.ts          — moved via `git mv`
```

### 2. Split of `utils/file-sharing/constants.ts`

Removed from file-sharing/constants.ts (they now live in utils/p2p/constants.ts):
- `BUFFER_THRESHOLD`
- `MAX_FRAME_SIZE`
- `MAX_HEADER_SIZE`

Remains in file-sharing/constants.ts:
- `FILE_SHARING_API`
- `FILE_SHARING_SIGNAL_PATH`
- `REPORTED_PAGE`
- `ZIP64_THRESHOLD`, `ZIP64_COUNT_THRESHOLD`
- `LARGE_FILE_THRESHOLD`, `VERY_LARGE_FILE_THRESHOLD`
- `formatFileSize`, `buildFileShareURL`, `buildSecretURL`

These are file-sharing-specific and stay where they are.

### 3. `SignalingClient` constructor change

Today `SignalingClient` hard-imports `FILE_SHARING_SIGNAL_PATH` and uses it inside `connect()`. That coupling is what pins it to file-sharing. The fix:

- Remove `import { FILE_SHARING_SIGNAL_PATH } from './constants'` inside signaling.ts.
- Add a constructor parameter: `new SignalingClient(signalPath: string)`.
- Store as `private signalPath: string`.
- `connect()` uses `this.signalPath` to build the WebSocket URL.

Call-site update (two places):
```diff
- const client = new SignalingClient()
+ const client = new SignalingClient(FILE_SHARING_SIGNAL_PATH)
```

The `FILE_SHARING_SIGNAL_PATH` constant continues to exist unchanged in `utils/file-sharing/constants.ts`. Future chambers will define their own constants (`SCREEN_SIGNAL_PATH`, etc.) — or, more likely, reuse one generic `/v1/file-sharing/signal/{slug}` endpoint since the backend signaling server is itself being generalized in PR 3.

### 4. `logger.ts` duplication (deliberate)

- `utils/file-sharing/logger.ts` stays — 7 hooks/components import from it.
- A new `utils/p2p/logger.ts` is created with identical body (different docstring).
- The transport triangle imports from `./logger` which now resolves to `utils/p2p/logger.ts`.

Ten trivial lines duplicated. Alternative (single source of truth with a re-export) adds an import indirection for no real benefit on a 15-line file. Revisit in a future cleanup pass if it grows.

### 5. Internal imports inside moved files

After `git mv`, the relative imports `./constants`, `./logger`, `./signaling` inside peer-connection.ts / signaling.ts / ws-relay.ts **resolve to the new location automatically** — no edits needed except the one described in §3.

### 6. External imports (16 call sites)

All 16 files that import from `utils/file-sharing/{peer-connection,signaling,ws-relay}` get their import paths updated to `utils/p2p/`. Nothing else in those files changes.

## Data-model / protocol implications

None. Wire protocol is unchanged. The signaling server's message schema is unchanged. Existing file-sharing sessions, once deployed, continue to connect identically.

## Tests

- All existing frontend tests pass unchanged.
- TypeScript compiler (`pnpm typecheck`) catches any missed import path.
- Manual smoke: spin up backend + frontend locally, do a file upload and a file download. Verify both complete.

## What this unblocks

- PR 3 can generalize signaling auth (the `utils/p2p/signaling.ts` client no longer pretends it's a file-sharing client).
- Future chambers (Screen, Messages, etc.) import the transport from `utils/p2p/` and implement their own chamber-specific logic in `utils/<chamber>/`.

## References consulted

- Polar upstream: no P2P code exists there. N/A.
- Chamber reference: N/A (infrastructure refactor, not a feature).

## Risk

Low — mechanical move. TypeScript catches any missed import path before the build succeeds, and `./verify.sh` won't pass if anything broke.

**Kill criterion:** any existing frontend test fails after the refactor. Revert and investigate.
