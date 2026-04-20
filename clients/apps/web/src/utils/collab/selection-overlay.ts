/**
 * Paints the selection UI onto the interactive canvas.
 *
 * Used by the demo (and by ``useCollabRoom`` once the chamber wires
 * Phase 3b in). The renderer provides a hook slot; this module wires
 * a stable-shaped drawer into it so the painting code stays out of
 * the React component.
 */

import type { ElementStore } from './element-store'
import type { SelectionState } from './selection'

const SELECTION_STROKE = '#4f46e5' // emerald/indigo pop; matches Excalidraw-ish selection blue
const MARQUEE_STROKE = '#4f46e5'
const MARQUEE_FILL = 'rgba(79, 70, 229, 0.08)'

export interface SelectionOverlayOptions {
  store: ElementStore
  selection: SelectionState
  /** Callback reading the current marquee rect in world coords, or
   *  ``null`` when no marquee is live. The select tool owns the
   *  state; this module just renders what it exposes. */
  getMarquee: () => {
    x: number
    y: number
    width: number
    height: number
  } | null
}

/** Build a paint function suitable for ``renderer.setInteractivePaint``.
 *  The returned function is stable across calls so the renderer can
 *  compare references to decide whether to repaint. */
export function makeSelectionOverlay(
  opts: SelectionOverlayOptions,
): (ctx: CanvasRenderingContext2D) => void {
  return (ctx) => {
    paintSelectedBounds(ctx, opts)
    paintMarquee(ctx, opts)
  }
}

function paintSelectedBounds(
  ctx: CanvasRenderingContext2D,
  { store, selection }: SelectionOverlayOptions,
): void {
  if (selection.size === 0) return
  ctx.save()
  ctx.strokeStyle = SELECTION_STROKE
  ctx.lineWidth = 1.5
  ctx.setLineDash([6, 4])
  for (const id of selection.snapshot) {
    const el = store.get(id)
    if (!el) continue
    ctx.save()
    ctx.translate(el.x, el.y)
    if (el.angle !== 0) {
      const cx = el.width / 2
      const cy = el.height / 2
      ctx.translate(cx, cy)
      ctx.rotate(el.angle)
      ctx.translate(-cx, -cy)
    }
    // Slight outset so the outline sits OUTSIDE the element stroke.
    const inset = -4
    ctx.strokeRect(inset, inset, el.width - inset * 2, el.height - inset * 2)
    ctx.restore()
  }
  ctx.restore()
}

function paintMarquee(
  ctx: CanvasRenderingContext2D,
  { getMarquee }: SelectionOverlayOptions,
): void {
  const m = getMarquee()
  if (!m || m.width === 0 || m.height === 0) return
  ctx.save()
  ctx.fillStyle = MARQUEE_FILL
  ctx.strokeStyle = MARQUEE_STROKE
  ctx.lineWidth = 1
  ctx.setLineDash([4, 2])
  ctx.fillRect(m.x, m.y, m.width, m.height)
  ctx.strokeRect(m.x, m.y, m.width, m.height)
  ctx.restore()
}
