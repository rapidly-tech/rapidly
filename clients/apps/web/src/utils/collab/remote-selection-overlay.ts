/**
 * Paints remote peers' selection rectangles in their own colour.
 *
 * Complements ``cursor-overlay.ts``: cursors show *where* each peer
 * is, selection rectangles show *what they've grabbed*. Both read
 * from the same ``PresenceSource`` so flipping the backend from the
 * in-memory stub to the real Awareness-backed source surfaces both
 * overlays at once.
 *
 * Design notes
 * ------------
 *  - Outline is a solid tinted rect, drawn slightly outset from the
 *    element's bounding box so it sits *outside* the stroke and never
 *    fights with the local user's dashed ``selection-overlay``.
 *  - Line width + inset are screen-constant so the outline reads the
 *    same at every zoom.
 *  - Multi-peer overlap is handled by painting in remote-list order.
 *    Colours mix via a low alpha so it's still legible when two peers
 *    hover the same element.
 */

import type { ElementStore } from './element-store'
import type { PresenceSource, RemotePresence } from './presence'
import type { Viewport } from './viewport'

export interface RemoteSelectionOverlayOptions {
  store: ElementStore
  source: PresenceSource
  getViewport: () => Viewport
}

/** Screen-pixel outset so the outline sits outside the element stroke,
 *  matching the local selection overlay's inset convention. Kept at 2
 *  (not 4) so remote outlines don't visually collide with the local
 *  user's dashed blue outline when the same element is selected by
 *  both. */
const OUTSET_SCREEN_PX = 2
const LINE_WIDTH_SCREEN_PX = 1.5

/** Alpha for the fill tint. Low enough that two peers hovering the
 *  same element produce a legible blend rather than one opaquing the
 *  other. */
const FILL_ALPHA = 0.1

export function makeRemoteSelectionOverlay(
  opts: RemoteSelectionOverlayOptions,
): (ctx: CanvasRenderingContext2D) => void {
  return (ctx) => {
    const remotes = opts.source.getRemotes()
    if (remotes.length === 0) return
    const vp = opts.getViewport()
    ctx.save()
    for (const remote of remotes) {
      if (!remote.selection || remote.selection.length === 0) continue
      paintOnePeer(ctx, remote, vp, opts.store)
    }
    ctx.restore()
  }
}

function paintOnePeer(
  ctx: CanvasRenderingContext2D,
  remote: RemotePresence,
  vp: Viewport,
  store: ElementStore,
): void {
  if (!remote.selection) return
  const outset = OUTSET_SCREEN_PX / vp.scale
  const lineWidth = LINE_WIDTH_SCREEN_PX / vp.scale

  ctx.save()
  ctx.strokeStyle = remote.user.color
  ctx.fillStyle = withAlpha(remote.user.color, FILL_ALPHA)
  ctx.lineWidth = lineWidth
  // No dash — a solid line visually distinguishes remote selections
  // from the local user's dashed selection rectangle.

  for (const id of remote.selection) {
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
    const x = -outset
    const y = -outset
    const w = el.width + outset * 2
    const h = el.height + outset * 2
    ctx.fillRect(x, y, w, h)
    ctx.strokeRect(x, y, w, h)
    ctx.restore()
  }

  ctx.restore()
}

/** Convert a ``#rrggbb`` colour + alpha in 0..1 into ``rgba(...)``.
 *  Defensive: if the input isn't a 7-char hex, fall back to the colour
 *  unchanged (canvas will treat it as opaque — good enough). */
function withAlpha(hex: string, alpha: number): string {
  if (hex.length !== 7 || hex[0] !== '#') return hex
  const r = parseInt(hex.slice(1, 3), 16)
  const g = parseInt(hex.slice(3, 5), 16)
  const b = parseInt(hex.slice(5, 7), 16)
  if (Number.isNaN(r) || Number.isNaN(g) || Number.isNaN(b)) return hex
  return `rgba(${r}, ${g}, ${b}, ${alpha})`
}
