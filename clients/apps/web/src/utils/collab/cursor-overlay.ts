/**
 * Paints remote peers' cursors (and optional name labels) onto the
 * interactive canvas.
 *
 * Cursor world coords ride on Awareness; the overlay just reads them
 * via the ``PresenceSource`` interface and projects them into screen
 * space via the shared viewport. Keeping the painter decoupled from
 * any specific backend lets the demo swap in a stub source and the
 * production code plug in the Awareness-backed one — same painter.
 *
 * Design
 * ------
 * The pointer shape is a small rounded triangle pointing up-left, sized
 * constant-in-screen-pixels so it reads the same at every zoom. Colour
 * comes from the remote's ``user.color`` (typically derived via
 * ``stableColor(clientId)``), so every peer agrees on which colour
 * belongs to whom without negotiation.
 */

import type { PresenceSource, RemotePresence } from './presence'
import type { Viewport } from './viewport'

export interface CursorOverlayOptions {
  source: PresenceSource
  getViewport: () => Viewport
  /** Whether to paint the name label next to each cursor. Default
   *  ``true``; the demo toggles it off for a cleaner static render. */
  showLabels?: boolean
}

const CURSOR_SIZE = 14 // screen pixels — tip-to-tail
const LABEL_PAD_X = 4
const LABEL_GAP_X = 10 // screen px between cursor tip and label start
const LABEL_FONT = '11px system-ui, -apple-system, sans-serif'

/** Build an interactive paint function that renders every remote
 *  cursor at its current world coords. Returns ``null``-if-empty so
 *  the renderer can compose multiple overlays cheaply. */
export function makeCursorOverlay(
  opts: CursorOverlayOptions,
): (ctx: CanvasRenderingContext2D) => void {
  return (ctx) => {
    const remotes = opts.source.getRemotes()
    if (remotes.length === 0) return
    const vp = opts.getViewport()
    ctx.save()
    for (const remote of remotes) {
      if (!remote.cursor) continue
      paintOneCursor(ctx, remote, vp, opts.showLabels ?? true)
    }
    ctx.restore()
  }
}

function paintOneCursor(
  ctx: CanvasRenderingContext2D,
  remote: RemotePresence,
  vp: Viewport,
  showLabel: boolean,
): void {
  const cursor = remote.cursor
  if (!cursor) return

  // The renderer paints into a world-space transform (ctx is already
  // scaled + translated to world units). We want screen-constant
  // sizes for the cursor, so divide by scale.
  const s = 1 / vp.scale
  const size = CURSOR_SIZE * s

  ctx.save()
  ctx.translate(cursor.x, cursor.y)

  // Rounded triangle pointer, tip at (0, 0) pointing up-left.
  ctx.fillStyle = remote.user.color
  ctx.strokeStyle = 'rgba(0, 0, 0, 0.35)'
  ctx.lineWidth = 1 * s
  ctx.lineJoin = 'round'
  ctx.beginPath()
  ctx.moveTo(0, 0)
  ctx.lineTo(size * 0.9, size * 0.35)
  ctx.lineTo(size * 0.35, size * 0.9)
  ctx.closePath()
  ctx.fill()
  ctx.stroke()

  if (showLabel && remote.user.name) {
    ctx.font = LABEL_FONT
    const metrics = ctx.measureText(remote.user.name)
    const labelW = metrics.width / vp.scale + (LABEL_PAD_X * 2) / vp.scale
    const labelH = 14 / vp.scale
    const gap = LABEL_GAP_X / vp.scale

    // Label sits just past the tail of the cursor.
    const lx = size * 0.9 + gap
    const ly = size * 0.35 - labelH / 2

    ctx.fillStyle = remote.user.color
    ctx.beginPath()
    roundRect(ctx, lx, ly, labelW, labelH, 3 / vp.scale)
    ctx.fill()

    ctx.fillStyle = '#ffffff'
    // Font has been scaled into world units via the canvas transform;
    // keep the same screen-pixel size by drawing with the world-space
    // font size.
    ctx.font = `${11 * s}px system-ui, -apple-system, sans-serif`
    ctx.textBaseline = 'middle'
    ctx.fillText(remote.user.name, lx + LABEL_PAD_X / vp.scale, ly + labelH / 2)
  }

  ctx.restore()
}

/** Minimal ``CanvasRenderingContext2D.roundRect`` shim — not all
 *  target browsers support the native method yet. Kept as a file-
 *  local helper so tests can mock the path without coupling to DOM. */
function roundRect(
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
