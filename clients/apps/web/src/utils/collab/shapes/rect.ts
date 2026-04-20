/**
 * Rectangle painter + hit-test for the Collab v2 renderer.
 *
 * Phase 1 only: axis-aligned, optionally rounded corners, plain stroke.
 * Rough-style jitter comes in Phase 2, not here.
 *
 * The ``pathFor`` function returns a Path2D in *element-local* coords
 * (origin at the rect's top-left). The renderer applies the element's
 * rotation + position via ``ctx.translate/rotate`` before stroking so
 * hit-testing can reuse the same Path2D by inverting the transform
 * on the query point instead of rebuilding the path.
 */

import type { RectElement } from '../elements'

/** Build the hit + paint Path2D in the element's own coordinate space.
 *  Caller positions/rotates the context before stroking. */
export function pathFor(el: RectElement): Path2D {
  const path = new Path2D()
  const { width, height } = el
  const r = Math.max(0, Math.min(el.roundness, Math.min(width, height) / 2))
  if (r === 0) {
    path.rect(0, 0, width, height)
    return path
  }
  // Rounded rectangle — ``ctx.roundRect`` is fine in the browser but
  // Path2D.roundRect isn't universal across older Safari, so use the
  // explicit path construction which has been supported forever.
  path.moveTo(r, 0)
  path.lineTo(width - r, 0)
  path.quadraticCurveTo(width, 0, width, r)
  path.lineTo(width, height - r)
  path.quadraticCurveTo(width, height, width - r, height)
  path.lineTo(r, height)
  path.quadraticCurveTo(0, height, 0, height - r)
  path.lineTo(0, r)
  path.quadraticCurveTo(0, 0, r, 0)
  path.closePath()
  return path
}

/** Paint a rect onto the given context. Assumes the context has had
 *  the element's world-space transform applied (translate to its x/y,
 *  rotate around its centre). The path is in element-local coords. */
export function paintRect(
  ctx: CanvasRenderingContext2D,
  el: RectElement,
  path: Path2D,
): void {
  ctx.save()
  applyStrokeStyle(ctx, el)
  if (el.fillColor !== 'transparent' && el.fillStyle !== 'none') {
    ctx.fillStyle = el.fillColor
    ctx.fill(path)
  }
  ctx.stroke(path)
  ctx.restore()
}

/** Shared style setup — kept here for now; hoists to shapes/common
 *  when a second shape lands. */
function applyStrokeStyle(
  ctx: CanvasRenderingContext2D,
  el: RectElement,
): void {
  ctx.strokeStyle = el.strokeColor
  ctx.lineWidth = el.strokeWidth
  ctx.globalAlpha = el.opacity / 100
  switch (el.strokeStyle) {
    case 'dashed':
      ctx.setLineDash([el.strokeWidth * 4, el.strokeWidth * 2])
      break
    case 'dotted':
      ctx.setLineDash([el.strokeWidth, el.strokeWidth * 2])
      break
    default:
      ctx.setLineDash([])
  }
  ctx.lineCap = 'round'
  ctx.lineJoin = 'round'
}
