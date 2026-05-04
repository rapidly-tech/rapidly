/**
 * Ellipse painter + hit-test for the Collab v2 renderer.
 *
 * Phase 1 only: smooth ellipse, no rough style. Rough-style jitter
 * (Phase 2) replaces the single ``ellipse()`` call with a seeded
 * Bezier approximation; the hit Path2D stays the smooth version so
 * pointer precision doesn't depend on the aesthetic.
 */

import type { EllipseElement } from '../elements'
import { makeRng, roughEllipse } from '../rough'
import { paintFill } from './fills'

export function pathFor(el: EllipseElement): Path2D {
  const path = new Path2D()
  const rx = el.width / 2
  const ry = el.height / 2

  if (el.roughness > 0) {
    roughEllipse(path, rx, ry, rx, ry, makeRng(el.seed), {
      roughness: el.roughness,
    })
    return path
  }

  // Path2D.ellipse: centre-x, centre-y, rx, ry, rotation, startAngle,
  // endAngle. Element-local origin is top-left, so centre lives at
  // (rx, ry). Rotation stays 0 here; the renderer applies the element
  // rotation via ctx.rotate before stroking.
  path.ellipse(rx, ry, rx, ry, 0, 0, Math.PI * 2)
  return path
}

export function paintEllipse(
  ctx: CanvasRenderingContext2D,
  el: EllipseElement,
  path: Path2D,
): void {
  ctx.save()
  applyStrokeStyle(ctx, el)
  paintFill(ctx, path, el, { width: el.width, height: el.height })
  ctx.stroke(path)
  ctx.restore()
}

function applyStrokeStyle(
  ctx: CanvasRenderingContext2D,
  el: EllipseElement,
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
