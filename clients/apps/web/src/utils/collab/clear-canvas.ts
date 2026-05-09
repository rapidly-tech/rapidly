/**
 * Clear-canvas helper for the Collab v2 whiteboard.
 *
 * Deletes every element in a single Yjs transaction so remote peers
 * see one atomic frame and the local Undo stack treats it as one
 * step. Locked elements **are** deleted — clear-canvas is a
 * deliberate, confirmation-gated action; the user has chosen to wipe
 * everything. (Compare with Delete, which respects locks because it
 * fires from a single keystroke.)
 *
 * Pure module — no React, no DOM. The whiteboard's palette command
 * confirms with the user via ``window.confirm`` and then calls in.
 */

import type { ElementStore } from './element-store'

/** Wipe every element. Returns the count of removed entries — useful
 *  for telemetry / a "Cleared N elements" toast. */
export function clearCanvas(store: ElementStore): number {
  const ids = store.list().map((el) => el.id)
  if (ids.length === 0) return 0
  store.deleteMany(ids)
  return ids.length
}
