/**
 * Cross-tab Yjs sync over ``BroadcastChannel``.
 *
 * Two tabs of the same Collab room would otherwise race the IndexedDB
 * snapshot — both load on mount, both write on every update, and a
 * fast edit in one tab is invisible to the other until a full snapshot
 * round-trips through the disk. ``BroadcastChannel`` lets them stream
 * Yjs updates directly so each tab sees the other's edits within a
 * frame, never touching the network.
 *
 * Same room id → same channel name. Different rooms get their own
 * channel so a user with two unrelated whiteboards open doesn't see
 * cross-talk.
 *
 * Origin tagging
 * --------------
 * Updates we receive over the channel are applied with
 * ``CROSS_TAB_ORIGIN``. Our own ``update`` listener checks the
 * transaction origin and skips broadcasting when it matches —
 * otherwise inbound updates would echo back to the sender and cycle
 * forever.
 *
 * Why BroadcastChannel and not a SharedWorker
 * -------------------------------------------
 * BroadcastChannel is a single-line wire-up, supported in every
 * evergreen browser, and has no startup cost. A SharedWorker would
 * also work but adds a separate JS context the tabs would have to
 * negotiate with — overkill for sub-megabyte Yjs updates that only
 * need fan-out.
 *
 * Initial sync
 * ------------
 * On open, each tab broadcasts its own state vector. Peers respond
 * with the diff (``encodeStateAsUpdate`` filtered by the sender's
 * vector). This is Yjs's standard two-step sync — the late-joining
 * tab advertises ""I have nothing"" and any older tab streams the
 * missing history back. Without this, the second tab would only sync
 * forward — past edits made before it opened wouldn't appear until
 * the next remote edit triggered a broadcast.
 *
 * Pure module — no React, no DOM. Tests inject a stub channel
 * factory so the controller can be exercised without ``jsdom``.
 */

import * as Y from 'yjs'

/** Origin tag attached to ``Y.applyUpdate`` calls fired from inbound
 *  cross-tab messages. Consumers (e.g. the persistence layer) can
 *  filter on this to avoid reflecting inbound updates back through a
 *  network provider. Exported so callers + tests can compare. */
export const CROSS_TAB_ORIGIN = Symbol('collab.v2.cross-tab')

/** Subset of ``BroadcastChannel`` we use. Lets tests inject a stub
 *  without ``jsdom`` shimming the real thing. */
export interface CrossTabChannel {
  postMessage(data: unknown): void
  addEventListener(
    type: 'message',
    listener: (e: { data: unknown }) => void,
  ): void
  removeEventListener(
    type: 'message',
    listener: (e: { data: unknown }) => void,
  ): void
  close(): void
}

export type CrossTabChannelFactory = (name: string) => CrossTabChannel | null

/** Default factory — instantiates a real ``BroadcastChannel`` when the
 *  global is available, otherwise returns null so the controller
 *  no-ops cleanly in SSR / unsupported browsers. */
export const defaultChannelFactory: CrossTabChannelFactory = (name) => {
  if (typeof BroadcastChannel === 'undefined') return null
  return new BroadcastChannel(name) as unknown as CrossTabChannel
}

export interface CrossTabSyncOptions {
  doc: Y.Doc
  /** Stable identifier — typically the Collab room slug. Channel name
   *  is derived from this so different rooms don't cross-talk. */
  roomId: string
  /** Channel factory injection point for tests. Production callers
   *  let it default to ``defaultChannelFactory``. */
  channelFactory?: CrossTabChannelFactory
}

export interface CrossTabSyncController {
  /** Tear down the channel + stop listening. Safe to call twice. */
  dispose(): void
  /** ``true`` when a real channel was opened (i.e. the browser
   *  supports BroadcastChannel and we aren't on the SSR fallback). */
  readonly active: boolean
}

interface SyncMessage {
  type: 'update' | 'state-vector'
  /** ``Uint8Array`` payload — Yjs update bytes for ``update``,
   *  encoded state vector for ``state-vector``. */
  payload: Uint8Array
}

/** Wire a doc to a BroadcastChannel for cross-tab fan-out. Returns a
 *  controller so the caller can dispose on unmount. Composes cleanly
 *  with the existing IndexedDB persistence layer — both fire on the
 *  same ``doc.update`` events, neither echoes the other. */
export function createCrossTabSync(
  opts: CrossTabSyncOptions,
): CrossTabSyncController {
  const factory = opts.channelFactory ?? defaultChannelFactory
  const channel = factory(channelNameFor(opts.roomId))
  if (!channel) {
    return { dispose: () => {}, active: false }
  }

  const onMessage = (e: { data: unknown }): void => {
    const msg = parseMessage(e.data)
    if (!msg) return
    if (msg.type === 'update') {
      Y.applyUpdate(opts.doc, msg.payload, CROSS_TAB_ORIGIN)
      return
    }
    if (msg.type === 'state-vector') {
      // Another tab announced its state vector — respond with the
      // diff so it catches up. Cheap (a single encode), bounded by
      // doc size. Skip empty diffs (the YJS no-op marker) so an idle
      // pair of tabs doesn't keep ping-ponging on unrelated joins.
      const diff = Y.encodeStateAsUpdate(opts.doc, msg.payload)
      if (diff.byteLength > 2) {
        channel.postMessage({ type: 'update', payload: diff })
      }
      return
    }
  }
  channel.addEventListener('message', onMessage)

  const onUpdate = (update: Uint8Array, origin: unknown): void => {
    // Skip inbound cross-tab updates so we don't echo. Persistence-
    // origin updates are local hydrations from disk, also skipped.
    if (origin === CROSS_TAB_ORIGIN) return
    channel.postMessage({ type: 'update', payload: update })
  }
  opts.doc.on('update', onUpdate)

  // Announce ourselves so any older tab streams missing updates back.
  // Sending our state vector means peers immediately know what we're
  // missing — no second round-trip required.
  channel.postMessage({
    type: 'state-vector',
    payload: Y.encodeStateVector(opts.doc),
  })

  let disposed = false
  return {
    dispose() {
      if (disposed) return
      disposed = true
      channel.removeEventListener('message', onMessage)
      opts.doc.off('update', onUpdate)
      channel.close()
    },
    active: true,
  }
}

/** Channel name from a room id. Exposed so tests can assert tabs in
 *  different rooms get different channels without knowing the prefix. */
export function channelNameFor(roomId: string): string {
  return `rapidly-collab-${roomId}`
}

/** Validate an inbound message. Inbound payloads come from a sibling
 *  tab so they're trusted, but we still reject malformed shapes so a
 *  bad extension or stale tab can't crash the listener. */
function parseMessage(data: unknown): SyncMessage | null {
  if (!data || typeof data !== 'object') return null
  const obj = data as Record<string, unknown>
  if (obj.type !== 'update' && obj.type !== 'state-vector') return null
  if (!(obj.payload instanceof Uint8Array)) return null
  return obj as unknown as SyncMessage
}
