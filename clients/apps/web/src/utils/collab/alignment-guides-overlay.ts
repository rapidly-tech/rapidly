/**
 * Paints alignment guides for the active drag gesture onto the
 * interactive canvas. Reads from a caller-supplied callback so the
 * overlay stays decoupled from where the guides come from — today
 * that's the select tool, but a future resize gesture might emit them
 * too.
 *
 * Guides are short dashed lines spanning from the topmost (or
 * leftmost) participating bbox edge to the bottommost (or rightmost),
 * at the world-space coord the snap pulled to. Stroke colour matches
 * the selection-overlay accent so the UI feels of one piece, with low
 * opacity so the guide reads as a hint, not a hard rule.
 *
 * The renderer applies the world transform before invoking this paint
 * function — every coord we draw is in world units.
 */

import type { SnapGuide } from './snap-to-objects'
import type { Viewport } from './viewport'

/** Stroke / dash sized so the guide stays one CSS pixel wide and
 *  the dash period stays consistent regardless of zoom. Caller supplies
 *  the live viewport so we can divide by scale. */
const GUIDE_STROKE_PX = 1
const GUIDE_DASH_PX: readonly [number, number] = [4, 3]
/** Same indigo as the selection overlay, kept faint to read as a hint. */
const GUIDE_COLOR = 'rgba(79, 70, 229, 0.55)'

export interface AlignmentGuidesOverlayOptions {
  /** Callback returning the live guide list. Empty array = paint
   *  nothing; the renderer still calls us so the overlay can clear
   *  cleanly when the snap drops away. */
  getGuides: () => readonly SnapGuide[]
  /** Live viewport so the dash pattern + line width stay screen-
   *  constant across zoom. */
  getViewport: () => Viewport
}

/** Build a paint function suitable for ``renderer.setInteractivePaint``.
 *  Returns a stable function reference; safe to compose with other
 *  overlays via a wrapper closure. */
export function makeAlignmentGuidesOverlay(
  opts: AlignmentGuidesOverlayOptions,
): (ctx: CanvasRenderingContext2D) => void {
  return (ctx) => {
    const guides = opts.getGuides()
    if (guides.length === 0) return
    const scale = opts.getViewport().scale
    if (scale <= 0) return

    ctx.save()
    ctx.strokeStyle = GUIDE_COLOR
    ctx.lineWidth = GUIDE_STROKE_PX / scale
    ctx.setLineDash([GUIDE_DASH_PX[0] / scale, GUIDE_DASH_PX[1] / scale])

    for (const guide of guides) {
      ctx.beginPath()
      if (guide.axis === 'x') {
        // Vertical line at world x = guide.world, spanning y = start..end.
        ctx.moveTo(guide.world, guide.start)
        ctx.lineTo(guide.world, guide.end)
      } else {
        // Horizontal line at world y = guide.world.
        ctx.moveTo(guide.start, guide.world)
        ctx.lineTo(guide.end, guide.world)
      }
      ctx.stroke()
    }

    ctx.restore()
  }
}
