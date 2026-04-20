/**
 * Freedraw (pen / pencil) shape adapter.
 *
 * ``points`` stores ``[x0, y0, p0, x1, y1, p1, ...]`` in element-local
 * coords with pressure ∈ [0, 1] per sample. The simple paint path
 * below renders at a constant stroke width; pressure-modulated width
 * comes with the Rough-style pass in Phase 2, which will sample the
 * pressure series and segment the stroke into variable-width pieces.
 *
 * We use quadratic smoothing between samples to hide pointer jitter —
 * common pen-tool trick: ``moveTo(p[0])``, then for each adjacent
 * pair (a, b) ``quadraticCurveTo(a, midpoint(a, b))``.
 */

import type { FreeDrawElement } from '../elements'

export function pathFor(el: FreeDrawElement): Path2D {
  const path = new Path2D()
  const pts = el.points
  // Each sample is (x, y, pressure) — stride 3.
  const stride = 3
  if (pts.length < stride) return path

  const xAt = (i: number) => pts[i * stride]
  const yAt = (i: number) => pts[i * stride + 1]
  const n = Math.floor(pts.length / stride)

  if (n === 1) {
    // Single-dot stroke — emit a tiny circle so it's visible.
    path.arc(xAt(0), yAt(0), Math.max(1, el.strokeWidth / 2), 0, Math.PI * 2)
    return path
  }

  path.moveTo(xAt(0), yAt(0))
  for (let i = 0; i < n - 1; i++) {
    const ax = xAt(i)
    const ay = yAt(i)
    const bx = xAt(i + 1)
    const by = yAt(i + 1)
    const midX = (ax + bx) / 2
    const midY = (ay + by) / 2
    path.quadraticCurveTo(ax, ay, midX, midY)
  }
  // Close up the last segment with a direct line to the final point.
  path.lineTo(xAt(n - 1), yAt(n - 1))
  return path
}

export function paintFreeDraw(
  ctx: CanvasRenderingContext2D,
  el: FreeDrawElement,
  path: Path2D,
): void {
  ctx.save()
  applyStrokeStyle(ctx, el)
  ctx.stroke(path)
  ctx.restore()
}

function applyStrokeStyle(
  ctx: CanvasRenderingContext2D,
  el: FreeDrawElement,
): void {
  ctx.strokeStyle = el.strokeColor
  ctx.lineWidth = el.strokeWidth
  ctx.globalAlpha = el.opacity / 100
  ctx.lineCap = 'round'
  ctx.lineJoin = 'round'
  // Freedraw ignores strokeStyle dashing — dashed pen strokes are
  // more novelty than utility and the jitter smoothing looks weird
  // with a dash pattern.
  ctx.setLineDash([])
}
