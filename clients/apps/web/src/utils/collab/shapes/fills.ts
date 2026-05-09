/**
 * Shared fill renderer for the Collab v2 shape painters.
 *
 * Every closed shape (rect, ellipse, diamond, frame, sticky) used to
 * inline the same ``ctx.fill(path)`` block, which only honoured the
 * ``solid`` and ``none`` ``fillStyle`` values — ``hatch``, ``cross-hatch``,
 * and ``dots`` were silently downgraded to a flat fill.
 *
 * This module owns the dispatch:
 *
 *  - ``solid``       — single ``ctx.fill(path)``.
 *  - ``hatch``       — diagonal parallel lines clipped to the path.
 *  - ``cross-hatch`` — two perpendicular hatch passes.
 *  - ``dots``        — round dots laid out on a grid, clipped to the path.
 *  - ``none``        — no-op, callers can still stroke the outline.
 *
 * Hachure lines are drawn over a rotated coordinate system whose
 * extents cover the shape's bounding-box diagonal, so a 45° pattern
 * fills the whole interior regardless of the shape's outline. The
 * caller's ``ctx.clip(path)`` keeps the strokes inside the visible
 * area.
 */

import type { FillStyle } from '../elements'

/** Minimal element shape this module needs. Keeping it structural so
 *  every concrete element (rect/ellipse/diamond/etc.) satisfies it
 *  without explicit casts. */
export interface FillTarget {
  fillColor: string
  fillStyle: FillStyle
  /** Used to scale the hatch line thickness so heavy strokes don't
   *  produce hair-thin hatches and vice versa. */
  strokeWidth: number
}

interface PaintOptions {
  /** Element-local AABB width. */
  width: number
  /** Element-local AABB height. */
  height: number
  /** Spacing in element-local units between hachure lines and dots.
   *  Default tuned to feel natural at 1× zoom; the renderer scales
   *  the canvas before calling so this doesn't need DPR adjustment. */
  spacing?: number
}

const DEFAULT_SPACING = 8

/** Paint the fill portion of a shape. Caller is responsible for the
 *  surrounding ``ctx.save() / restore()`` that protects strokeStyle,
 *  globalAlpha, etc. — this only mutates ``fillStyle`` /
 *  ``strokeStyle`` / ``lineWidth`` / current path / current clip. */
export function paintFill(
  ctx: CanvasRenderingContext2D,
  path: Path2D,
  el: FillTarget,
  { width, height, spacing = DEFAULT_SPACING }: PaintOptions,
): void {
  if (el.fillColor === 'transparent' || el.fillStyle === 'none') return

  if (el.fillStyle === 'solid') {
    ctx.fillStyle = el.fillColor
    ctx.fill(path)
    return
  }

  // Patterned fills: clip to the shape so the hatching/dots stay
  // inside the outline. Save before clip so the caller's outer
  // restore() rolls back the clip too — every shape painter wraps
  // this call in its own save/restore already.
  ctx.save()
  ctx.clip(path)

  if (el.fillStyle === 'dots') {
    ctx.fillStyle = el.fillColor
    const r = Math.max(1, Math.min(2, el.strokeWidth * 0.5))
    for (let y = spacing / 2; y < height; y += spacing) {
      for (let x = spacing / 2; x < width; x += spacing) {
        ctx.beginPath()
        ctx.arc(x, y, r, 0, Math.PI * 2)
        ctx.fill()
      }
    }
    ctx.restore()
    return
  }

  // hatch / cross-hatch — diagonal parallel lines.
  ctx.strokeStyle = el.fillColor
  ctx.lineWidth = Math.max(1, el.strokeWidth * 0.6)
  ctx.setLineDash([])
  ctx.lineCap = 'round'

  drawDiagonalLines(ctx, width, height, spacing, 45)
  if (el.fillStyle === 'cross-hatch') {
    drawDiagonalLines(ctx, width, height, spacing, -45)
  }

  ctx.restore()
}

/** Draw an unbounded set of parallel lines at the given angle (in
 *  degrees), spaced ``spacing`` units apart, covering an area large
 *  enough to fill any AABB up to ``width`` × ``height`` after rotation.
 *  Caller's clip narrows them to the actual shape. */
function drawDiagonalLines(
  ctx: CanvasRenderingContext2D,
  width: number,
  height: number,
  spacing: number,
  angleDeg: number,
): void {
  ctx.save()
  ctx.translate(width / 2, height / 2)
  ctx.rotate((angleDeg * Math.PI) / 180)
  // Diagonal of the AABB — once rotated, horizontal lines spanning
  // ±diag cover the whole rotated quad regardless of angle.
  const diag = Math.hypot(width, height)
  for (let y = -diag; y <= diag; y += spacing) {
    ctx.beginPath()
    ctx.moveTo(-diag, y)
    ctx.lineTo(diag, y)
    ctx.stroke()
  }
  ctx.restore()
}
