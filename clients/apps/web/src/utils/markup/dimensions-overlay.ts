/**
 * Dimensions overlay — paints a small ``W × H`` label below every
 * selected element so the user can see live size + position numbers
 * while resizing or repositioning.
 *
 * Mirrors the shape of ``selection-overlay.ts`` so the host wires
 * the returned paint function into the same compositing slot:
 *
 *   r.setInteractivePaint((ctx) => {
 *     selectionPaint(ctx)
 *     dimensionsPaint(ctx)        // ← new
 *     ...
 *   })
 *
 * The pure ``dimensionLabels`` helper is split out so it can be
 * unit-tested without touching a canvas.
 */

import type { ElementStore } from './element-store'
import type { SelectionState } from './selection'
import type { UnitFormatter } from './units'
import type { Viewport } from './viewport'

export interface DimensionsOverlayOptions {
  store: ElementStore
  selection: SelectionState
  getViewport: () => Viewport
  /** Toggle the whole overlay off without unwiring it; the host
   *  exposes a command-palette entry that flips this. */
  getEnabled: () => boolean
  /** Optional formatter for the dimension labels. When omitted, the
   *  overlay falls back to whole-pixel rendering — the historical
   *  default. Hosts wire ``makeFormatter(boardScale)`` from
   *  ``units.ts`` once the board has a calibrated scale (see
   *  ``calibration.ts``) so labels read in engineering units. */
  getFormatter?: () => UnitFormatter
}

export interface DimensionLabel {
  /** Element id this label belongs to. */
  id: string
  /** Screen-space position the label's top-left aligns to. */
  screenX: number
  screenY: number
  /** Pre-formatted ``"W × H"`` string. */
  text: string
}

/** World-space rect for a single element + viewport, projected to
 *  the screen-space label position. Returned as an array so callers
 *  can iterate without re-computing per element. */
export function dimensionLabels(
  elements: Array<{
    id: string
    x: number
    y: number
    width: number
    height: number
  }>,
  selectedIds: ReadonlySet<string>,
  viewport: Viewport,
  /** Vertical pixel gap below the element where the label sits. */
  gapPx = 6,
  /** Optional unit-aware formatter for each axis. When provided, the
   *  label text becomes ``"<W formatted> × <H formatted>"``; otherwise
   *  the historical whole-pixel formatter is used. */
  formatter?: UnitFormatter,
): DimensionLabel[] {
  const out: DimensionLabel[] = []
  for (const el of elements) {
    if (!selectedIds.has(el.id)) continue
    // World → screen: multiply by scale, subtract scroll.
    const screenX = (el.x - viewport.scrollX) * viewport.scale
    const screenBottomY =
      (el.y + el.height - viewport.scrollY) * viewport.scale + gapPx
    const text = formatter
      ? `${formatter.format(el.width)} × ${formatter.format(el.height)}`
      : formatDimensions(el.width, el.height)
    out.push({
      id: el.id,
      screenX,
      screenY: screenBottomY,
      text,
    })
  }
  return out
}

/** Format a ``W × H`` label. Uses the multiplication sign (× / U+00D7)
 *  rather than ``x`` so dimensions read like Figma / Sketch. Values
 *  round to whole pixels — sub-pixel resize jitter would distract. */
export function formatDimensions(width: number, height: number): string {
  return `${Math.round(width)} × ${Math.round(height)}`
}

/** Build a paint function suitable for the renderer's interactive
 *  paint slot. Stable across calls so the renderer can compare
 *  references when deciding to repaint. */
export function makeDimensionsOverlay(
  opts: DimensionsOverlayOptions,
): (ctx: CanvasRenderingContext2D) => void {
  return (ctx) => {
    if (!opts.getEnabled()) return
    const ids = opts.selection.snapshot
    if (ids.size === 0) return
    const viewport = opts.getViewport()
    // Sample each id to a {x,y,width,height} record. The store
    // returns the live element; we pass through only the geometry
    // ``dimensionLabels`` needs.
    const elements: Array<{
      id: string
      x: number
      y: number
      width: number
      height: number
    }> = []
    for (const id of ids) {
      const el = opts.store.get(id)
      if (!el) continue
      elements.push({
        id,
        x: el.x,
        y: el.y,
        width: el.width,
        height: el.height,
      })
    }
    const formatter = opts.getFormatter?.()
    const labels = dimensionLabels(elements, ids, viewport, 6, formatter)

    // The selection overlay paints in world space (the renderer
    // applies the viewport transform before invoking it). We want
    // labels at constant screen size, so reset the transform and
    // paint in screen-pixel coords.
    ctx.save()
    ctx.setTransform(1, 0, 0, 1, 0, 0)
    ctx.font = '11px ui-sans-serif, system-ui, sans-serif'
    ctx.textBaseline = 'top'
    for (const label of labels) {
      const padX = 4
      const padY = 2
      const metrics = ctx.measureText(label.text)
      const w = metrics.width + padX * 2
      const h = 14
      ctx.fillStyle = 'rgba(15, 23, 42, 0.92)' // slate-900/92
      // Round-rect when supported; bail to a regular rect otherwise.
      ctx.beginPath()
      const rrect = (
        ctx as unknown as {
          roundRect?: (
            x: number,
            y: number,
            w: number,
            h: number,
            r: number,
          ) => void
        }
      ).roundRect
      if (rrect) rrect.call(ctx, label.screenX, label.screenY, w, h, 3)
      else ctx.rect(label.screenX, label.screenY, w, h)
      ctx.fill()
      ctx.fillStyle = '#ffffff'
      ctx.fillText(label.text, label.screenX + padX, label.screenY + padY)
    }
    ctx.restore()
  }
}
