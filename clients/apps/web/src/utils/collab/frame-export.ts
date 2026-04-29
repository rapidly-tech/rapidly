/**
 * Frame-level export — Phase 18 follow-up.
 *
 * Reuses ``exportToPNG`` / ``exportToSVG`` / ``exportToJSON`` against
 * the subset of elements that belong to a frame: the frame itself
 * plus every id in its ``childIds``. The bbox automatically follows
 * because the existing exporters call ``computeBounds`` on the element
 * list — pass it the subset and you get the frame's footprint.
 *
 * Pure module — no DOM, no canvas. ``CollabWhiteboard`` palette
 * commands consult these helpers when the user has a single frame
 * selected.
 */

import type { CollabElement } from './elements'
import { isFrame } from './elements'

/** Return the elements that belong to ``frameId``: the frame plus
 *  every id in its ``childIds``. Children are returned in their
 *  paint-order position from ``elements`` so PNG / SVG export
 *  preserves stacking. */
export function elementsForFrame(
  elements: readonly CollabElement[],
  frameId: string,
): CollabElement[] {
  const frame = elements.find((el) => el.id === frameId)
  if (!frame || !isFrame(frame)) return []
  const childSet = new Set(frame.childIds)
  const out: CollabElement[] = []
  // Iterate the canonical paint order; preserves z-stack regardless
  // of childIds[] ordering.
  for (const el of elements) {
    if (el.id === frameId) {
      out.push(el)
    } else if (childSet.has(el.id)) {
      out.push(el)
    }
  }
  return out
}

/** ``true`` when ``id`` resolves to a frame element. Convenience for
 *  palette guards that want ""only show this command when the
 *  selection is exactly one frame"". */
export function isFrameId(
  elements: readonly CollabElement[],
  id: string,
): boolean {
  const el = elements.find((e) => e.id === id)
  return !!el && isFrame(el)
}
