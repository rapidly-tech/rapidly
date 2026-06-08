/**
 * Paints the selection UI onto the interactive canvas.
 *
 * Used by the demo (and by ``useCollabRoom`` once the chamber wires
 * Phase 3b in). The renderer provides a hook slot; this module wires
 * a stable-shaped drawer into it so the painting code stays out of
 * the React component.
 */

import type { ElementStore } from './element-store'
import { HANDLE_SIZE_FOR_PRECISION } from './pointer-preference'
import { handleRotatedPositions } from './resize'
import { rotationHandlePosition } from './rotation'
import type { SelectionState } from './selection'
import type { Viewport } from './viewport'

const SELECTION_STROKE = '#4f46e5' // emerald/indigo selection pop
const MARQUEE_STROKE = '#4f46e5'
const MARQUEE_FILL = 'rgba(79, 70, 229, 0.08)'

/** Handles stay this many screen pixels wide regardless of zoom.
 *  Divided by the viewport scale inside the painter so the world-
 *  space rect we stroke ends up at the right screen size. */
const DEFAULT_HANDLE_SCREEN_SIZE_PX = HANDLE_SIZE_FOR_PRECISION.fine

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
  /** Live viewport so the handle painter can scale handle squares
   *  to a constant screen size regardless of zoom. */
  getViewport: () => Viewport
  /** Screen-pixel handle size override. Defaults to the desktop
   *  (``fine``) preset. Touch hosts pass the ``coarse`` preset from
   *  ``pointer-preference.ts`` so handles stay tappable. */
  getHandleSizePx?: () => number
  /** Vertices of the in-progress lasso polygon (flat ``[x0,y0,…]``)
   *  in world coords, or ``null`` when no lasso gesture is active.
   *  The lasso tool owns the state; this overlay just renders it. */
  getLasso?: () => readonly number[] | null
}

/** Build a paint function suitable for ``renderer.setInteractivePaint``.
 *  The returned function is stable across calls so the renderer can
 *  compare references to decide whether to repaint. */
export function makeSelectionOverlay(
  opts: SelectionOverlayOptions,
): (ctx: CanvasRenderingContext2D) => void {
  return (ctx) => {
    paintSelectedBounds(ctx, opts)
    paintHandles(ctx, opts)
    paintMarquee(ctx, opts)
    paintLasso(ctx, opts)
  }
}

/** Paint the 8 resize handles on a single selected element. Multi-
 *  selection resize (a shared group bounds) is a Phase 4 follow-up;
 *  for now we simply don't render handles when more than one is
 *  selected so the overlay stays clean. */
function paintHandles(
  ctx: CanvasRenderingContext2D,
  { store, selection, getViewport, getHandleSizePx }: SelectionOverlayOptions,
): void {
  if (selection.size !== 1) return
  const [id] = selection.snapshot
  const el = store.get(id)
  if (!el) return
  // Locked elements show the dashed-grey outline + lock badge but no
  // interactive handles — there's nothing the user can do with them
  // until they unlock. Matches the select-tool pointerdown gate.
  if (el.locked) return
  const vp = getViewport()
  const sizePx = getHandleSizePx?.() ?? DEFAULT_HANDLE_SCREEN_SIZE_PX
  const worldSize = sizePx / vp.scale
  const half = worldSize / 2
  const handles = handleRotatedPositions(el)
  ctx.save()
  ctx.lineWidth = 1 / vp.scale
  for (const h of Object.values(handles)) {
    ctx.fillStyle = '#ffffff'
    ctx.strokeStyle = SELECTION_STROKE
    ctx.fillRect(h.x - half, h.y - half, worldSize, worldSize)
    ctx.strokeRect(h.x - half, h.y - half, worldSize, worldSize)
  }
  // Rotation handle — a circle above the n handle, connected by a
  // short line so the user reads it as ""attached"" to the selection
  // rather than free-floating UI.
  const rot = rotationHandlePosition(el, vp)
  const radius = (sizePx * 0.55) / vp.scale
  ctx.beginPath()
  ctx.moveTo(handles.n.x, handles.n.y)
  ctx.lineTo(rot.x, rot.y)
  ctx.stroke()
  ctx.fillStyle = '#ffffff'
  ctx.strokeStyle = SELECTION_STROKE
  ctx.beginPath()
  ctx.arc(rot.x, rot.y, radius, 0, Math.PI * 2)
  ctx.fill()
  ctx.stroke()
  ctx.restore()
}

function paintSelectedBounds(
  ctx: CanvasRenderingContext2D,
  { store, selection, getViewport }: SelectionOverlayOptions,
): void {
  if (selection.size === 0) return
  const vp = getViewport()
  ctx.save()
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
    // Locked elements get a solid grey outline so they're visually
    // distinct from the editable dashed-blue selection.
    const locked = el.locked === true
    ctx.strokeStyle = locked ? '#64748b' : SELECTION_STROKE
    ctx.lineWidth = 1.5
    ctx.setLineDash(locked ? [] : [6, 4])
    const inset = -4
    ctx.strokeRect(inset, inset, el.width - inset * 2, el.height - inset * 2)
    if (locked) {
      paintLockBadge(ctx, el.width, el.height, vp.scale)
    }
    ctx.restore()
  }
  ctx.restore()
}

/** Tiny lock glyph at the element's top-right, screen-constant size.
 *  Lives on the overlay layer so it doesn't force every shape adapter
 *  to know about locks. */
function paintLockBadge(
  ctx: CanvasRenderingContext2D,
  width: number,
  _height: number,
  viewportScale: number,
): void {
  const size = 14 / viewportScale
  const pad = 4 / viewportScale
  const x = width - size - pad
  const y = -size - pad
  ctx.save()
  ctx.setLineDash([])
  // Background pill so the glyph reads on any fill colour.
  ctx.fillStyle = '#64748b'
  ctx.beginPath()
  roundRectPath(ctx, x, y, size, size, 3 / viewportScale)
  ctx.fill()
  // Simple lock silhouette drawn in white on top.
  ctx.fillStyle = '#ffffff'
  const sx = x + size * 0.5
  const sy = y + size * 0.55
  const bodyW = size * 0.55
  const bodyH = size * 0.4
  ctx.fillRect(sx - bodyW / 2, sy - bodyH / 2, bodyW, bodyH)
  // Shackle — an open rounded arc above the body.
  ctx.strokeStyle = '#ffffff'
  ctx.lineWidth = 1.4 / viewportScale
  ctx.beginPath()
  ctx.arc(sx, sy - bodyH / 2, bodyW * 0.45, Math.PI, 0)
  ctx.stroke()
  ctx.restore()
}

function roundRectPath(
  ctx: CanvasRenderingContext2D,
  x: number,
  y: number,
  w: number,
  h: number,
  r: number,
): void {
  const rr = Math.min(r, w / 2, h / 2)
  ctx.moveTo(x + rr, y)
  ctx.lineTo(x + w - rr, y)
  ctx.quadraticCurveTo(x + w, y, x + w, y + rr)
  ctx.lineTo(x + w, y + h - rr)
  ctx.quadraticCurveTo(x + w, y + h, x + w - rr, y + h)
  ctx.lineTo(x + rr, y + h)
  ctx.quadraticCurveTo(x, y + h, x, y + h - rr)
  ctx.lineTo(x, y + rr)
  ctx.quadraticCurveTo(x, y, x + rr, y)
  ctx.closePath()
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

function paintLasso(
  ctx: CanvasRenderingContext2D,
  { getLasso }: SelectionOverlayOptions,
): void {
  const poly = getLasso?.()
  if (!poly || poly.length < 4) return
  ctx.save()
  ctx.fillStyle = MARQUEE_FILL
  ctx.strokeStyle = MARQUEE_STROKE
  ctx.lineWidth = 1
  ctx.setLineDash([4, 2])
  ctx.lineJoin = 'round'
  ctx.beginPath()
  ctx.moveTo(poly[0], poly[1])
  for (let i = 2; i < poly.length; i += 2) {
    ctx.lineTo(poly[i], poly[i + 1])
  }
  ctx.closePath()
  ctx.fill()
  ctx.stroke()
  ctx.restore()
}
