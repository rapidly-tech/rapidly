/**
 * Read-only scrollbars overlay for the Collab v2 whiteboard.
 *
 * Sits in the bottom + right edges of the canvas and reflects where
 * the visible viewport falls within the union AABB of all elements
 * (or the visible region itself, if it extends past every element).
 * Excalidraw's parity feature for orientation when the canvas is
 * larger than the viewport.
 *
 * Drag-to-scroll is intentionally out of scope here: the existing
 * Hand tool, space-drag, middle-click, and trackpad pan all already
 * move the viewport. Scrollbars in this v1 are a position indicator,
 * not a control surface.
 */

import type { CollabElement } from './elements'
import type { Viewport } from './viewport'

const TRACK_THICKNESS = 6
const TRACK_INSET = 4
const TRACK_FILL = 'rgba(15, 23, 42, 0.05)' // slate-900 @ 5%
const THUMB_FILL = 'rgba(15, 23, 42, 0.35)' // slate-900 @ 35%
const MIN_THUMB_PX = 24

export interface ScrollbarsOptions {
  getElements: () => readonly CollabElement[]
  getViewport: () => Viewport
}

/** Returns a paint callback compatible with ``Renderer.setScreenPaint``.
 *  The callback skips itself entirely when there's nothing to scroll
 *  through (no elements + viewport at origin) so an empty canvas
 *  doesn't grow chrome that has no information to convey. */
export function makeScrollbarsOverlay(
  opts: ScrollbarsOptions,
): (
  ctx: CanvasRenderingContext2D,
  size: { width: number; height: number },
) => void {
  return (ctx, size) => {
    const elements = opts.getElements()
    const vp = opts.getViewport()
    const viewW = size.width / vp.scale
    const viewH = size.height / vp.scale
    const view = {
      x: vp.scrollX,
      y: vp.scrollY,
      width: viewW,
      height: viewH,
    }
    const content = unionAabb(elements)
    // Skip the chrome when the viewport already contains everything
    // and is anchored at the content origin — there's nothing to
    // scroll towards yet.
    if (!content && view.x === 0 && view.y === 0) return

    // Total extent the scrollbars represent: the content AABB unioned
    // with the current view, so the thumb stays inside the track even
    // when the user has panned past every element.
    const total = content
      ? unionRects(content, view)
      : view

    const trackY = size.height - TRACK_THICKNESS - TRACK_INSET
    const trackX = size.width - TRACK_THICKNESS - TRACK_INSET
    // Keep the bottom-right corner free so a horizontal + vertical
    // track don't overlap and print on top of each other.
    const horizMaxLen = size.width - TRACK_INSET * 2 - TRACK_THICKNESS - 2
    const vertMaxLen = size.height - TRACK_INSET * 2 - TRACK_THICKNESS - 2

    paintTrack(
      ctx,
      TRACK_INSET,
      trackY,
      horizMaxLen,
      TRACK_THICKNESS,
    )
    paintThumb(
      ctx,
      TRACK_INSET,
      trackY,
      horizMaxLen,
      TRACK_THICKNESS,
      view.x - total.x,
      view.width,
      total.width,
      'h',
    )

    paintTrack(
      ctx,
      trackX,
      TRACK_INSET,
      TRACK_THICKNESS,
      vertMaxLen,
    )
    paintThumb(
      ctx,
      trackX,
      TRACK_INSET,
      TRACK_THICKNESS,
      vertMaxLen,
      view.y - total.y,
      view.height,
      total.height,
      'v',
    )
  }
}

function paintTrack(
  ctx: CanvasRenderingContext2D,
  x: number,
  y: number,
  w: number,
  h: number,
): void {
  ctx.save()
  ctx.fillStyle = TRACK_FILL
  roundRect(ctx, x, y, w, h, TRACK_THICKNESS / 2)
  ctx.fill()
  ctx.restore()
}

function paintThumb(
  ctx: CanvasRenderingContext2D,
  x: number,
  y: number,
  w: number,
  h: number,
  viewOffset: number,
  viewSpan: number,
  totalSpan: number,
  orientation: 'h' | 'v',
): void {
  if (totalSpan <= 0 || viewSpan <= 0) return
  const trackLen = orientation === 'h' ? w : h
  // Proportional thumb length; clamped to a minimum so very-zoomed-out
  // views still produce a draggable hint.
  const proportional = (viewSpan / totalSpan) * trackLen
  const thumbLen = Math.max(MIN_THUMB_PX, Math.min(trackLen, proportional))
  // Offset within the track. ``viewOffset`` is in world units; turn it
  // into a 0..1 fraction of the slack space the thumb can move within.
  const slackWorld = Math.max(0, totalSpan - viewSpan)
  const fraction = slackWorld === 0 ? 0 : viewOffset / slackWorld
  const thumbOffset = (trackLen - thumbLen) * Math.max(0, Math.min(1, fraction))

  ctx.save()
  ctx.fillStyle = THUMB_FILL
  if (orientation === 'h') {
    roundRect(ctx, x + thumbOffset, y, thumbLen, h, h / 2)
  } else {
    roundRect(ctx, x, y + thumbOffset, w, thumbLen, w / 2)
  }
  ctx.fill()
  ctx.restore()
}

interface Rect {
  x: number
  y: number
  width: number
  height: number
}

/** Union AABB of every element, or ``null`` for an empty canvas. */
export function unionAabb(elements: readonly CollabElement[]): Rect | null {
  let minX = Infinity
  let minY = Infinity
  let maxX = -Infinity
  let maxY = -Infinity
  for (const el of elements) {
    if (el.x < minX) minX = el.x
    if (el.y < minY) minY = el.y
    if (el.x + el.width > maxX) maxX = el.x + el.width
    if (el.y + el.height > maxY) maxY = el.y + el.height
  }
  if (!Number.isFinite(minX)) return null
  return { x: minX, y: minY, width: maxX - minX, height: maxY - minY }
}

function unionRects(a: Rect, b: Rect): Rect {
  const x = Math.min(a.x, b.x)
  const y = Math.min(a.y, b.y)
  return {
    x,
    y,
    width: Math.max(a.x + a.width, b.x + b.width) - x,
    height: Math.max(a.y + a.height, b.y + b.height) - y,
  }
}

/** Path2D.roundRect is missing on older Safari; the explicit
 *  construction here matches what we already use elsewhere in the
 *  whiteboard for the same reason. */
function roundRect(
  ctx: CanvasRenderingContext2D,
  x: number,
  y: number,
  w: number,
  h: number,
  r: number,
): void {
  const rad = Math.max(0, Math.min(r, w / 2, h / 2))
  ctx.beginPath()
  ctx.moveTo(x + rad, y)
  ctx.lineTo(x + w - rad, y)
  ctx.quadraticCurveTo(x + w, y, x + w, y + rad)
  ctx.lineTo(x + w, y + h - rad)
  ctx.quadraticCurveTo(x + w, y + h, x + w - rad, y + h)
  ctx.lineTo(x + rad, y + h)
  ctx.quadraticCurveTo(x, y + h, x, y + h - rad)
  ctx.lineTo(x, y + rad)
  ctx.quadraticCurveTo(x, y, x + rad, y)
  ctx.closePath()
}
