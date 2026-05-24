/**
 * Frame containment — Phase 18 follow-up.
 *
 * A frame's ``childIds`` array is the authoritative ownership record.
 * The plan calls this out explicitly: ""Elements outside this array
 * but inside the frame's bounds are NOT considered children (makes
 * drag-in/drag-out an explicit action, not a render-time test)"".
 *
 * This module updates that record after a drag-move commits. When an
 * element's centre lands inside a frame's bbox, the frame adopts it.
 * When it lands outside any frame, the previous owner releases it.
 *
 * Why centre-of-element rather than full-containment
 * --------------------------------------------------
 * Full containment (every corner inside the frame) would force users
 * to drag elements deep into a frame to hand them over, which feels
 * sticky. Centre-of-element is the standard drag-into-group rule
 * and matches what most users expect.
 *
 * Pure module — no React, no DOM. The select tool calls in after the
 * move gesture commits.
 */

import type { ElementStore } from './element-store'
import { isFrame } from './elements'

/** AABB hit-test in world coords. Frames are axis-aligned for the
 *  purpose of containment regardless of their visual rotation —
 *  rotated frames containing children would otherwise be a confusing
 *  user-experience trap. */
function frameContains(
  frame: { x: number; y: number; width: number; height: number },
  pointX: number,
  pointY: number,
): boolean {
  return (
    pointX >= frame.x &&
    pointX <= frame.x + frame.width &&
    pointY >= frame.y &&
    pointY <= frame.y + frame.height
  )
}

/** Topmost (highest zIndex) frame whose bbox contains ``(worldX,
 *  worldY)``. Returns null when no frame matches — the caller treats
 *  that as ""no parent"". */
export function frameAtPoint(
  elements: readonly { id: string; type: string }[],
  worldX: number,
  worldY: number,
  // ``elements`` is the store's typed list; this signature stays loose
  // so tests can supply lighter fixtures.
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
): any | null {
  let best: {
    id: string
    zIndex: number
    x: number
    y: number
    width: number
    height: number
  } | null = null
  for (const el of elements as Array<{
    id: string
    type: string
    x: number
    y: number
    width: number
    height: number
    zIndex: number
  }>) {
    if (el.type !== 'frame') continue
    if (!frameContains(el, worldX, worldY)) continue
    if (!best || el.zIndex > best.zIndex) best = el
  }
  return best
}

/** Recompute frame membership for every id in ``movedIds``. Each
 *  element's centre decides which (if any) frame owns it after the
 *  move; the store's ``childIds`` arrays update in a single
 *  transaction so remote peers see one atomic frame.
 *
 *  Frames themselves are skipped — a frame inside another frame is a
 *  Phase-18b follow-up; for now top-level frames are independent.
 *
 *  Returns the count of memberships that actually changed. */
export function updateFrameMembership(
  store: ElementStore,
  movedIds: ReadonlySet<string>,
): number {
  if (movedIds.size === 0) return 0
  const all = store.list()
  const frames = all.filter(isFrame)
  if (frames.length === 0) return 0

  // Build a working copy of every frame's childIds so we can mutate
  // and only commit the diff at the end.
  const next: Map<string, string[]> = new Map(
    frames.map((f) => [f.id, [...f.childIds]]),
  )

  for (const id of movedIds) {
    if (!next.has(id) === false) continue // skip moved frames
    const el = store.get(id)
    if (!el) continue
    if (el.type === 'frame') continue
    const cx = el.x + el.width / 2
    const cy = el.y + el.height / 2
    const newOwner = frameAtPoint(all, cx, cy)
    // Strip from any frame currently claiming it.
    for (const [fid, ids] of next) {
      if (newOwner && fid === newOwner.id) continue
      const idx = ids.indexOf(id)
      if (idx >= 0) ids.splice(idx, 1)
    }
    if (newOwner) {
      const ids = next.get(newOwner.id) ?? []
      if (!ids.includes(id)) ids.push(id)
      next.set(newOwner.id, ids)
    }
  }

  // Diff + commit. Skip frames whose childIds didn't change so we
  // don't bump their version for nothing.
  const patches: { id: string; patch: { childIds: string[] } }[] = []
  for (const f of frames) {
    const updated = next.get(f.id) ?? []
    if (childIdsEqual(f.childIds, updated)) continue
    patches.push({ id: f.id, patch: { childIds: updated } })
  }
  if (patches.length === 0) return 0
  store.transact(() => {
    store.updateMany(patches)
  })
  return patches.length
}

function childIdsEqual(a: readonly string[], b: readonly string[]): boolean {
  if (a.length !== b.length) return false
  for (let i = 0; i < a.length; i++) if (a[i] !== b[i]) return false
  return true
}
