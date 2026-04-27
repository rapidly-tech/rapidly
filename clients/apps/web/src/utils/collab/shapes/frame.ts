/**
 * Frame shape adapter — Phase 18 (Excalidraw-style containers).
 *
 * A frame is a labelled rectangle that holds child elements (tracked
 * by ``childIds`` on the model). The renderer just paints the
 * rectangle + label here; the parent/child relationship is enforced
 * by the select tool's drag-into / drag-out logic, which lands in a
 * follow-up — this PR only ships the visual.
 *
 * Visual conventions
 * ------------------
 *  - Thin dashed outline so the frame reads as ""structure"" rather
 *    than a drawing element.
 *  - Name label in a small bar above the top-left corner. The bar's
 *    background uses the frame's stroke colour at low alpha so the
 *    label survives any underlying canvas colour.
 */

import type { FrameElement } from '../elements'

/** Element-local Path2D — just the AABB. The label sits outside this
 *  path so hit-tests against the frame body don't accidentally pick
 *  up label clicks; that's a UX preference matching Excalidraw. */
export function pathFor(el: FrameElement): Path2D {
  const path = new Path2D()
  path.rect(0, 0, el.width, el.height)
  return path
}

const LABEL_HEIGHT = 18
const LABEL_PADDING = 6
const LABEL_FONT = '12px Cascadia, Menlo, monospace'

export function paintFrame(
  ctx: CanvasRenderingContext2D,
  el: FrameElement,
  path: Path2D,
): void {
  ctx.save()
  ctx.globalAlpha = el.opacity / 100

  // Frame body — dashed outline. No fill: a frame's purpose is to
  // contain other elements, so an opaque body would hide them.
  ctx.strokeStyle = el.strokeColor
  ctx.lineWidth = el.strokeWidth
  ctx.setLineDash([8, 4])
  ctx.stroke(path)

  // Reset the dash for the label so the bar reads as a solid ribbon.
  ctx.setLineDash([])

  // Label bar above the top-left. Background uses the stroke colour at
  // low alpha so the label always reads.
  const text = (el.name ?? '').trim() || 'Frame'
  ctx.font = LABEL_FONT
  const textWidth = ctx.measureText(text).width
  const barWidth = textWidth + LABEL_PADDING * 2
  const barX = 0
  const barY = -LABEL_HEIGHT - 2
  ctx.globalAlpha = (el.opacity / 100) * 0.85
  ctx.fillStyle = el.strokeColor
  ctx.fillRect(barX, barY, barWidth, LABEL_HEIGHT)
  ctx.globalAlpha = el.opacity / 100
  ctx.fillStyle = '#ffffff'
  ctx.textBaseline = 'middle'
  ctx.textAlign = 'left'
  ctx.fillText(text, barX + LABEL_PADDING, barY + LABEL_HEIGHT / 2)

  ctx.restore()
}
