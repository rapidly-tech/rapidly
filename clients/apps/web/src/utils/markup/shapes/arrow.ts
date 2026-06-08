/**
 * Arrow shape adapter.
 *
 * Path2D traces the element-local ``points`` polyline plus an
 * arrowhead at either end when configured. Rough-style aesthetic
 * lands in Phase 2; bindings (endpoint snaps to another shape's
 * anchor) land in Phase 6 — ``ArrowElement.startBinding`` /
 * ``endBinding`` are stored on the element but the shape adapter
 * doesn't consume them. The arrowhead-bearing head is sized relative
 * to ``strokeWidth`` so dashed / bold arrows don't look unbalanced.
 */

import type { ArrowElement, ArrowHead } from '../elements'
import { makeRng, roughLine } from '../rough'

const HEAD_LENGTH_PX = 14
const HEAD_WIDTH_PX = 10

export function pathFor(el: ArrowElement): Path2D {
  const path = new Path2D()
  const pts = el.points
  if (pts.length < 4) return path

  if (el.roughness > 0) {
    // Rough polyline between consecutive points, same seed so the
    // shape wobbles identically across peers. Arrowheads below are
    // drawn straight — a jittered triangle reads badly at small
    // sizes.
    const rng = makeRng(el.seed)
    const opts = { roughness: el.roughness }
    for (let i = 0; i < pts.length - 2; i += 2) {
      roughLine(path, pts[i], pts[i + 1], pts[i + 2], pts[i + 3], rng, opts)
    }
  } else {
    path.moveTo(pts[0], pts[1])
    for (let i = 2; i < pts.length; i += 2) {
      path.lineTo(pts[i], pts[i + 1])
    }
  }
  // Arrowheads are painted as extra sub-paths so fill + stroke can
  // both honour them — a filled triangle reads as an arrow, whereas
  // a stroke-only V reads as a caret.
  const sx0 = pts[0]
  const sy0 = pts[1]
  const sx1 = pts[2]
  const sy1 = pts[3]
  const ex0 = pts[pts.length - 2]
  const ey0 = pts[pts.length - 1]
  const ex1 = pts[pts.length - 4]
  const ey1 = pts[pts.length - 3]
  if (el.startArrowhead) {
    drawHead(path, sx1, sy1, sx0, sy0, el.startArrowhead, el.strokeWidth)
  }
  if (el.endArrowhead !== null && el.endArrowhead !== undefined) {
    drawHead(path, ex1, ey1, ex0, ey0, el.endArrowhead, el.strokeWidth)
  }
  return path
}

/** Draw an arrowhead at ``(tipX, tipY)`` pointing in the direction
 *  away from ``(fromX, fromY)``. Head style decides the shape. */
function drawHead(
  path: Path2D,
  fromX: number,
  fromY: number,
  tipX: number,
  tipY: number,
  style: ArrowHead,
  strokeWidth: number,
): void {
  if (!style) return
  const dx = tipX - fromX
  const dy = tipY - fromY
  const len = Math.hypot(dx, dy)
  if (len === 0) return
  const ux = dx / len
  const uy = dy / len
  // Perpendicular unit vector.
  const nx = -uy
  const ny = ux

  // Scale head to stroke width so bold arrows keep proportion, but
  // clamp to a sensible minimum so thin arrows still get a visible head.
  const headLen = Math.max(HEAD_LENGTH_PX, strokeWidth * 4)
  const headWid = Math.max(HEAD_WIDTH_PX, strokeWidth * 3)
  const baseX = tipX - ux * headLen
  const baseY = tipY - uy * headLen

  switch (style) {
    case 'triangle': {
      path.moveTo(tipX, tipY)
      path.lineTo(baseX + nx * (headWid / 2), baseY + ny * (headWid / 2))
      path.lineTo(baseX - nx * (headWid / 2), baseY - ny * (headWid / 2))
      path.closePath()
      break
    }
    case 'dot': {
      const r = Math.max(3, strokeWidth)
      path.moveTo(tipX + r, tipY)
      path.arc(tipX, tipY, r, 0, Math.PI * 2)
      break
    }
    case 'bar': {
      path.moveTo(tipX + nx * (headWid / 2), tipY + ny * (headWid / 2))
      path.lineTo(tipX - nx * (headWid / 2), tipY - ny * (headWid / 2))
      break
    }
  }
}

export function paintArrow(
  ctx: CanvasRenderingContext2D,
  el: ArrowElement,
  path: Path2D,
): void {
  ctx.save()
  applyStrokeStyle(ctx, el)
  ctx.fillStyle = el.strokeColor
  // Filled triangle head paints naturally when we fill the closed
  // sub-path; the line itself is open so fill doesn't affect it.
  ctx.fill(path)
  ctx.stroke(path)
  ctx.restore()
}

function applyStrokeStyle(
  ctx: CanvasRenderingContext2D,
  el: ArrowElement,
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
