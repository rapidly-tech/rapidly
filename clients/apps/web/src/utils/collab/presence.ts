/**
 * Presence model for the Collab v2 whiteboard.
 *
 * Presence = "who is here right now and where is their cursor / what
 * do they have selected". It lives outside the Yjs doc — every peer
 * publishes its own state via Yjs Awareness (encrypted and replay-
 * protected by the existing provider envelope). Awareness state is
 * ephemeral: when a peer disconnects, its entry disappears, and the
 * overlay stops painting it.
 *
 * Two presence sources
 * --------------------
 *  - ``awarenessPresenceSource(awareness, localClientId)`` — production
 *    adapter. Wraps a real Yjs ``Awareness`` instance. Filters out the
 *    local client's own state on read so we don't draw our own cursor
 *    over our OS cursor.
 *  - ``inMemoryPresenceSource()`` — tests + demo. A plain Map-backed
 *    implementation you can push fake peers into.
 *
 * Both implement the same ``PresenceSource`` interface so consumers
 * (the cursor overlay, the follow-me controller) don't care which is
 * wired up. That's the seam the demo uses to show a fake peer without
 * spinning up a real WebRTC provider.
 */

import type { Awareness } from 'y-protocols/awareness'

import type { Viewport } from './viewport'

/** Identity of one peer in a session. ``color`` is derived from the
 *  Yjs ``clientID`` (stableColor) so everyone agrees on which peer is
 *  which colour without extra coordination. */
export interface PresenceUser {
  id: string
  name?: string
  color: string
}

/** Shape of the local state we publish each frame. Cursor coords are
 *  **world coords**, not screen pixels — remote peers reproject to
 *  their own viewport, so zoom / pan do not distort shared cursors. */
export interface LocalPresence {
  user: PresenceUser
  cursor?: { x: number; y: number }
  /** Ids of elements the local user currently has selected. Empty /
   *  undefined means nothing selected. Broadcasting lets remote peers
   *  render soft selection rectangles with the owner's colour. */
  selection?: readonly string[]
  /** Optional viewport broadcast for the follow-me feature. Remotes
   *  watching this peer project these coords into their own renderer. */
  viewport?: Viewport
}

/** One remote peer's current state as seen by us. ``clientId`` is the
 *  Yjs ``Awareness.clientID`` — a random 32-bit integer per doc
 *  connection; it's opaque to UI but useful as a stable key. */
export interface RemotePresence {
  clientId: number
  user: PresenceUser
  cursor?: { x: number; y: number }
  selection?: readonly string[]
  /** Viewport the remote peer is currently looking at. Present only
   *  when the peer has opted into broadcasting it (follow-me mode). */
  viewport?: Viewport
}

/** Abstract handle over a presence backend. Consumers depend on this
 *  interface only; the Awareness-vs-in-memory choice is made at wire-
 *  up time. */
export interface PresenceSource {
  /** Current remotes (excluding the local peer). Returned list is a
   *  snapshot — safe to iterate without locking. */
  getRemotes(): readonly RemotePresence[]
  /** Subscribe to change events — called whenever any remote's state
   *  updates or a peer appears / disappears. The returned disposer
   *  unsubscribes. */
  subscribe(fn: () => void): () => void
  /** Publish the local state. ``undefined`` fields are dropped so a
   *  cursor of ``undefined`` explicitly hides the local cursor from
   *  remotes (useful when the pointer leaves the canvas). */
  setLocal(state: LocalPresence): void
}

// ── Stable colour from clientId ──────────────────────────────────────

/** A short curated palette — readable on both light and dark canvas,
 *  chosen to be distinguishable at glance. ``stableColor`` maps every
 *  ``clientID`` into this palette deterministically so every peer
 *  agrees on the colour for every other peer without negotiating. */
export const PRESENCE_PALETTE = [
  '#e03131', // red
  '#2f9e44', // green
  '#1971c2', // blue
  '#f08c00', // amber
  '#9c36b5', // violet
  '#ae3ec9', // plum
  '#0ca678', // teal
  '#d6336c', // pink
] as const

/** Deterministic colour for a given ``clientId``. Pure function; same
 *  id always maps to the same palette slot. Using a multiplicative
 *  hash mixes low-entropy sequential ids (rare but possible in tests)
 *  across the palette. */
export function stableColor(clientId: number): string {
  // Multiplicative hash (Knuth's constant * 2^32). Keeps small ids
  // from clustering on one palette slot.
  const h = (clientId * 2654435761) >>> 0
  return PRESENCE_PALETTE[h % PRESENCE_PALETTE.length]
}

// ── In-memory source ─────────────────────────────────────────────────

export interface InMemoryPresenceSource extends PresenceSource {
  pushRemote(presence: RemotePresence): void
  removeRemote(clientId: number): void
  /** Current local state (for assertions in tests). */
  readonly local: LocalPresence | null
}

/** Map-backed presence source. Tests and the demo wire fake peers
 *  into this without needing a Yjs doc. Calls to ``setLocal`` are
 *  stored but never broadcast anywhere — the demo doesn't need to. */
export function inMemoryPresenceSource(): InMemoryPresenceSource {
  const remotes = new Map<number, RemotePresence>()
  const listeners = new Set<() => void>()
  let local: LocalPresence | null = null

  const emit = (): void => {
    for (const fn of listeners) fn()
  }

  return {
    getRemotes: () => Array.from(remotes.values()),
    subscribe(fn) {
      listeners.add(fn)
      return () => {
        listeners.delete(fn)
      }
    },
    setLocal(state) {
      local = state
      emit()
    },
    pushRemote(p) {
      remotes.set(p.clientId, p)
      emit()
    },
    removeRemote(id) {
      if (remotes.delete(id)) emit()
    },
    get local() {
      return local
    },
  }
}

// ── Awareness-backed source ──────────────────────────────────────────

/** Production adapter over Yjs ``Awareness``. Filters out the local
 *  client's own state on read. Writes go through ``setLocalState`` so
 *  the provider's outbound awareness handler picks them up and
 *  encrypts them onto the wire.
 *
 *  Remote states that are missing ``user.id`` / ``user.color`` are
 *  dropped — we treat them as a peer that hasn't initialised yet. */
export function awarenessPresenceSource(
  awareness: Awareness,
  localClientId: number,
): PresenceSource {
  return {
    getRemotes() {
      const out: RemotePresence[] = []
      for (const [clientId, raw] of awareness.getStates()) {
        if (clientId === localClientId) continue
        const parsed = parseRemote(clientId, raw)
        if (parsed) out.push(parsed)
      }
      return out
    },
    subscribe(fn) {
      const listener = (): void => fn()
      awareness.on('update', listener)
      awareness.on('change', listener)
      return () => {
        awareness.off('update', listener)
        awareness.off('change', listener)
      }
    },
    setLocal(state) {
      // Strip undefined so remote peers' JSON shape matches the
      // published schema exactly and there's no ambiguity between
      // "absent" and "set to undefined".
      const out: Record<string, unknown> = { user: state.user }
      if (state.cursor) out.cursor = state.cursor
      if (state.selection && state.selection.length > 0) {
        out.selection = [...state.selection]
      }
      if (state.viewport) {
        out.viewport = {
          scale: state.viewport.scale,
          scrollX: state.viewport.scrollX,
          scrollY: state.viewport.scrollY,
        }
      }
      awareness.setLocalState(out)
    },
  }
}

/** Validate + narrow one raw awareness state. Returns ``null`` when
 *  the state is missing required fields — caller should skip it. */
function parseRemote(clientId: number, raw: unknown): RemotePresence | null {
  if (!raw || typeof raw !== 'object') return null
  const r = raw as Record<string, unknown>
  const user = r.user
  if (!user || typeof user !== 'object') return null
  const u = user as Record<string, unknown>
  if (typeof u.id !== 'string' || typeof u.color !== 'string') return null
  const presence: RemotePresence = {
    clientId,
    user: {
      id: u.id,
      color: u.color,
      ...(typeof u.name === 'string' ? { name: u.name } : {}),
    },
  }
  if (
    r.cursor &&
    typeof r.cursor === 'object' &&
    typeof (r.cursor as { x?: unknown }).x === 'number' &&
    typeof (r.cursor as { y?: unknown }).y === 'number' &&
    Number.isFinite((r.cursor as { x: number }).x) &&
    Number.isFinite((r.cursor as { y: number }).y)
  ) {
    presence.cursor = {
      x: (r.cursor as { x: number }).x,
      y: (r.cursor as { y: number }).y,
    }
  }
  if (
    Array.isArray(r.selection) &&
    (r.selection as unknown[]).every((s) => typeof s === 'string')
  ) {
    presence.selection = r.selection as string[]
  }
  if (r.viewport && typeof r.viewport === 'object') {
    const v = r.viewport as Record<string, unknown>
    if (
      typeof v.scale === 'number' &&
      typeof v.scrollX === 'number' &&
      typeof v.scrollY === 'number' &&
      Number.isFinite(v.scale) &&
      Number.isFinite(v.scrollX) &&
      Number.isFinite(v.scrollY)
    ) {
      presence.viewport = {
        scale: v.scale,
        scrollX: v.scrollX,
        scrollY: v.scrollY,
      }
    }
  }
  return presence
}
