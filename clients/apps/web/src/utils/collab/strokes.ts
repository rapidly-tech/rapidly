/**
 * Stroke data + rendering helpers for the Collab whiteboard (PR 19).
 *
 * Strokes live in a ``Y.Array<Stroke>`` keyed ``"strokes"`` on the shared
 * doc. Each stroke is a snapshot — once committed by the author it is
 * never mutated. That matches the CRDT model well: concurrent authors
 * simply push independent entries and Yjs's Array merges them.
 *
 * Points are stored as a flat number array (``[x0, y0, x1, y1, ...]``)
 * rather than ``{x, y}`` objects to halve JSON overhead — a typical
 * stroke has 40-200 points and we broadcast at ~60fps while drawing.
 */

export interface Stroke {
  /** Author identifier (Yjs clientID, stringified). Drives colour + undo
   *  ownership if we ever add it. */
  by: string
  /** Flat [x0, y0, x1, y1, ...] in canvas-local CSS pixels. */
  pts: number[]
  /** HSL hue, 0..360. Derived from ``by`` so the same peer keeps a
   *  stable colour across strokes. */
  hue: number
  /** Line width in CSS pixels. */
  w: number
}

export function hueFor(clientID: number): number {
  // Golden-angle hash — same function as PresenceStrip so the stroke
  // colour matches the peer pill in the presence bar.
  return (clientID * 137.508) % 360
}

/** Narrow runtime guard — the Y.Array can hold anything anyone pushes. */
export function isStroke(x: unknown): x is Stroke {
  if (!x || typeof x !== 'object') return false
  const obj = x as Record<string, unknown>
  return (
    typeof obj.by === 'string' &&
    Array.isArray(obj.pts) &&
    (obj.pts as unknown[]).every((n) => typeof n === 'number') &&
    typeof obj.hue === 'number' &&
    typeof obj.w === 'number'
  )
}

/** Paint one stroke on a 2D canvas context. Pure function — no state. */
export function paintStroke(ctx: CanvasRenderingContext2D, s: Stroke): void {
  if (s.pts.length < 2) return
  ctx.lineWidth = s.w
  ctx.lineCap = 'round'
  ctx.lineJoin = 'round'
  ctx.strokeStyle = `hsl(${s.hue} 70% 45%)`
  ctx.beginPath()
  ctx.moveTo(s.pts[0], s.pts[1])
  // A single-dot stroke (move but no draws) shows as a dot because
  // lineCap is 'round'; issuing a 0-length lineTo gives it something
  // to render against.
  if (s.pts.length === 2) {
    ctx.lineTo(s.pts[0], s.pts[1])
  } else {
    for (let i = 2; i < s.pts.length; i += 2) {
      ctx.lineTo(s.pts[i], s.pts[i + 1])
    }
  }
  ctx.stroke()
}

/** Paint every stroke + the in-progress local stroke onto a canvas.
 *  Clears first. Separated from the component so tests can exercise it. */
export function repaint(
  ctx: CanvasRenderingContext2D,
  width: number,
  height: number,
  committed: readonly Stroke[],
  inProgress: Stroke | null,
): void {
  ctx.clearRect(0, 0, width, height)
  for (const s of committed) paintStroke(ctx, s)
  if (inProgress) paintStroke(ctx, inProgress)
}
