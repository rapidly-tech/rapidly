/**
 * Frame export — render a single frame (and only the elements it
 * contains) as a PNG. The whole-scene export in ``export.ts``
 * rasterises every element on the canvas; this module narrows that
 * to the subtree owned by one frame so designers can hand off
 * individual screens / artboards without first deleting the
 * surrounding context.
 *
 * Pure layout ``frameDescendants`` is split out so callers can
 * unit-test selection logic without spinning up a canvas.
 */

import type { ElementStore } from './element-store'
import type { CollabElement } from './elements'
import {
  exportToJSON,
  exportToPNG,
  type ExportedScene,
  type ExportPNGOptions,
} from './export'
import { exportToSVG, type ExportSVGOptions } from './svg-export'

/** Returns the frame element followed by every element listed in
 *  its ``childIds`` (in the order the frame declares them). The
 *  frame itself is included so the export includes its background /
 *  border treatment. Missing ids are skipped silently — a frame
 *  whose children were deleted still exports cleanly. Returns an
 *  empty array when the frame doesn't exist. */
export function frameDescendants(
  store: ElementStore,
  frameId: string,
): CollabElement[] {
  const frame = store.get(frameId)
  if (!frame || frame.type !== 'frame') return []
  const out: CollabElement[] = [frame]
  for (const childId of (frame as { childIds: string[] }).childIds) {
    const child = store.get(childId)
    if (child) out.push(child)
  }
  return out
}

/** Rasterise just the frame's subtree to a PNG blob. Returns
 *  ``null`` when the frame doesn't exist or has no renderable
 *  content (matches ``exportToPNG``'s short-circuit on empty
 *  bounds). */
export async function exportFrameAsPng(
  store: ElementStore,
  frameId: string,
  options: ExportPNGOptions = {},
): Promise<Blob | null> {
  const elements = frameDescendants(store, frameId)
  if (elements.length === 0) return null
  return exportToPNG(elements, options)
}

/** Render just the frame's subtree to an SVG document. Returns
 *  ``null`` when the frame doesn't exist; ``exportToSVG`` itself
 *  always returns a string (zero-sized for empty input), so the
 *  null case is purely the missing-frame guard. */
export function exportFrameAsSvg(
  store: ElementStore,
  frameId: string,
  options: ExportSVGOptions = {},
): string | null {
  const elements = frameDescendants(store, frameId)
  if (elements.length === 0) return null
  return exportToSVG(elements, options)
}

/** Wrap just the frame's subtree in the JSON export envelope.
 *  Returns ``null`` when the frame doesn't exist. */
export function exportFrameAsJson(
  store: ElementStore,
  frameId: string,
): ExportedScene | null {
  const elements = frameDescendants(store, frameId)
  if (elements.length === 0) return null
  return exportToJSON(elements)
}
