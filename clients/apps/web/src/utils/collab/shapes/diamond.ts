/**
 * Diamond shape adapter.
 *
 * A four-point shape whose vertices sit at the midpoints of the
 * element's bounding box: top, right, bottom, left. Same stroke /
 * fill rules as rect; rough-style jitter lands in Phase 2 of the
 * aesthetic pass.
 */

import type { DiamondElement } from '../elements'

export function pathFor(el: DiamondElement): Path2D {
  const path = new Path2D()
  const { width, height } = el
  const hw = width / 2
  const hh = height / 2
  // Roundness clamped to a safe fraction of the shortest edge so a
  // user pasting 999 doesn't collapse the path.
  const r = Math.max(0, Math.min(el.roundness ?? 0, Math.min(hw, hh) / 2))

  if (r === 0) {
    path.moveTo(hw, 0)
    path.lineTo(width, hh)
    path.lineTo(hw, height)
    path.lineTo(0, hh)
    path.closePath()
    return path
  }

  // Rounded diamond — trim each vertex with a quadratic curve. The
  // rounding offset is parametric along each edge so the curve
  // length is consistent per corner.
  const t = r / Math.hypot(hw, hh)
  path.moveTo(hw - t * hw, t * hh)
  path.quadraticCurveTo(hw, 0, hw + t * hw, t * hh)
  path.lineTo(width - t * hw, hh - t * hh)
  path.quadraticCurveTo(width, hh, width - t * hw, hh + t * hh)
  path.lineTo(hw + t * hw, height - t * hh)
  path.quadraticCurveTo(hw, height, hw - t * hw, height - t * hh)
  path.lineTo(t * hw, hh + t * hh)
  path.quadraticCurveTo(0, hh, t * hw, hh - t * hh)
  path.closePath()
  return path
}

export function paintDiamond(
  ctx: CanvasRenderingContext2D,
  el: DiamondElement,
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

function applyStrokeStyle(
  ctx: CanvasRenderingContext2D,
  el: DiamondElement,
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
