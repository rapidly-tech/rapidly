/**
 * Line shape adapter.
 *
 * Uses the element's ``points`` array ([x0, y0, x1, y1]) in element-
 * local coords. Width/height on the element hold the AABB, which the
 * renderer uses for hit-testing + rotation anchor; the path itself
 * follows ``points``.
 */

import type { LineElement } from '../elements'

export function pathFor(el: LineElement): Path2D {
  const path = new Path2D()
  const pts = el.points
  if (pts.length < 4) {
    // Malformed line — nothing to draw, but returning an empty
    // Path2D keeps the renderer's assumption "every element has a
    // Path2D" intact.
    return path
  }
  path.moveTo(pts[0], pts[1])
  for (let i = 2; i < pts.length; i += 2) {
    path.lineTo(pts[i], pts[i + 1])
  }
  return path
}

export function paintLine(
  ctx: CanvasRenderingContext2D,
  el: LineElement,
  path: Path2D,
): void {
  ctx.save()
  applyStrokeStyle(ctx, el)
  ctx.stroke(path)
  ctx.restore()
}

function applyStrokeStyle(
  ctx: CanvasRenderingContext2D,
  el: LineElement,
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
