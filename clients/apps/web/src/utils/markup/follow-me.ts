/**
 * Follow-me controller for the Collab v2 whiteboard.
 *
 * "Follow" mode pins the local viewport to a selected remote peer —
 * whenever that peer pans or zooms, the follower's renderer mirrors
 * the move. It's a one-way lock: the follower can still interact
 * (click, type), but any manual pan / zoom immediately breaks the
 * follow so the user isn't fighting the camera.
 *
 * Mechanism
 * ---------
 * Viewports ride on the existing ``PresenceSource`` (Phase 11). This
 * module adds no wire protocol of its own — it just subscribes to
 * the shared source, filters for the targeted peer, and calls an
 * ``apply`` callback with a ``Viewport`` snapshot each time that
 * peer's state changes. The caller plugs the callback into whatever
 * renderer / viewport ref it owns.
 *
 * The controller is intentionally UI-agnostic so the demo page and
 * the production ``useCollabRoom`` hook share the same code path.
 */

import type { PresenceSource, RemotePresence } from './presence'
import type { Viewport } from './viewport'

export interface FollowMeOptions {
  source: PresenceSource
  /** Applied with the target peer's viewport each time it changes.
   *  Host is responsible for actually moving the renderer — the
   *  controller just reads and dispatches. */
  apply: (viewport: Viewport) => void
}

export interface FollowMeController {
  /** Lock onto a peer. Passing ``null`` clears follow mode. Calling
   *  with the same id twice is a no-op. */
  setTarget(clientId: number | null): void
  /** Currently-followed peer, or ``null`` when not following. */
  current(): number | null
  /** Tear down the subscription. Callers who create a controller in a
   *  hook should run this in cleanup so the listener doesn't leak. */
  dispose(): void
}

/** Build a follow-me controller. Starts inactive (no target). Host
 *  code typically pairs it with a UI element (dropdown, avatar strip)
 *  that calls ``setTarget`` on click. */
export function createFollowMeController(
  opts: FollowMeOptions,
): FollowMeController {
  let target: number | null = null
  // Remember the last viewport we applied so we don't churn the host
  // renderer with identical callbacks when a remote updates an
  // unrelated field (e.g. only its cursor moved).
  let lastApplied: Viewport | null = null

  const tick = (): void => {
    if (target === null) return
    const remote = findRemote(opts.source.getRemotes(), target)
    if (!remote || !remote.viewport) return
    if (viewportsEqual(remote.viewport, lastApplied)) return
    lastApplied = { ...remote.viewport }
    opts.apply(remote.viewport)
  }

  const off = opts.source.subscribe(tick)

  return {
    setTarget(clientId) {
      if (clientId === target) return
      target = clientId
      lastApplied = null
      // Run once immediately so the follower snaps to the peer's
      // current viewport without waiting for the next awareness
      // update.
      tick()
    },
    current() {
      return target
    },
    dispose() {
      off()
      target = null
      lastApplied = null
    },
  }
}

/** Pure helper — returns the matching remote or ``null``. Exposed for
 *  tests / callers that want to inspect state outside the controller. */
export function findRemote(
  remotes: readonly RemotePresence[],
  clientId: number,
): RemotePresence | null {
  for (const r of remotes) {
    if (r.clientId === clientId) return r
  }
  return null
}

/** Structural viewport equality. Used by the controller to dedupe
 *  applied updates. Tolerates ``null`` on either side so the caller
 *  can compare against ""nothing applied yet"". */
export function viewportsEqual(
  a: Viewport | null | undefined,
  b: Viewport | null | undefined,
): boolean {
  if (!a || !b) return a === b
  return (
    a.scale === b.scale && a.scrollX === b.scrollX && a.scrollY === b.scrollY
  )
}
