/**
 * Clean-room seeded jitter — the "rough" / hand-drawn aesthetic.
 *
 * Not a fork of Rough.js. We read the public algorithm (seeded PRNG,
 * perturbed-midpoint Bezier for lines, sampled-point loop for
 * ellipses) and re-implemented it from scratch to match our
 * ``clean_room_policy`` memo. The numbers chosen here are our own —
 * they aim for "close to Excalidraw's feel" without claiming pixel
 * parity.
 *
 * Seed discipline
 * ---------------
 * Every shape stores a ``seed`` on the element. Rough output is a
 * pure function of (seed, geometry, roughness), so every peer paints
 * the exact same wobble. Re-painting a single element re-uses the
 * same seed so the wobble doesn't re-roll on every frame.
 */

export type RoughLevel = 0 | 1 | 2

/** Mulberry32 — 32-bit seeded PRNG. Cheap, decent statistical
 *  properties, well above what we need for visual jitter. */
export function makeRng(seed: number): () => number {
  let a = seed >>> 0
  return () => {
    a = (a + 0x6d2b79f5) >>> 0
    let t = a
    t = Math.imul(t ^ (t >>> 15), t | 1)
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61)
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296
  }
}

/** Offset magnitude for a given roughness level, scaled to the
 *  shape's size so a 10-pixel line and a 1000-pixel line wobble
 *  visually comparably. */
function offsetFor(level: RoughLevel, reference: number): number {
  if (level === 0) return 0.4 + 0.01 * reference
  if (level === 1) return 1 + 0.02 * reference
  return 2 + 0.04 * reference
}

interface RoughOpts {
  roughness: RoughLevel
  /** Multi-stroke for the "drawn twice" pencil feel. Defaults true at
   *  roughness 1–2 and false at 0. */
  doubleStroke?: boolean
}

/** Perturb a 2D point by ``amount`` in a random direction, using
 *  ``rng`` so the result is seeded-reproducible. */
function perturb(
  x: number,
  y: number,
  amount: number,
  rng: () => number,
): [number, number] {
  const angle = rng() * Math.PI * 2
  const d = rng() * amount
  return [x + Math.cos(angle) * d, y + Math.sin(angle) * d]
}

/** Append a rough Bezier line from A to B into ``path``. The curve
 *  has two interior control points, each perturbed around the true
 *  midpoint — that's the classic Rough.js-style wobble. */
export function roughLine(
  path: Path2D,
  ax: number,
  ay: number,
  bx: number,
  by: number,
  rng: () => number,
  opts: RoughOpts,
): void {
  const length = Math.hypot(bx - ax, by - ay)
  const off = offsetFor(opts.roughness, length)

  const drawOne = () => {
    // Jitter the endpoints a little too — the start of an Excalidraw
    // line isn't perfectly on the grid either.
    const [sx, sy] = perturb(ax, ay, off * 0.5, rng)
    const [ex, ey] = perturb(bx, by, off * 0.5, rng)

    // Two control points along the line, each pulled to a random
    // perpendicular offset. Without these the line would be straight
    // between the perturbed endpoints — the jittered mids give the
    // "scratchy pen" look.
    const mx1 = ax + (bx - ax) / 3
    const my1 = ay + (by - ay) / 3
    const mx2 = ax + (2 * (bx - ax)) / 3
    const my2 = ay + (2 * (by - ay)) / 3

    const [c1x, c1y] = perturb(mx1, my1, off, rng)
    const [c2x, c2y] = perturb(mx2, my2, off, rng)

    path.moveTo(sx, sy)
    path.bezierCurveTo(c1x, c1y, c2x, c2y, ex, ey)
  }

  drawOne()
  if (opts.doubleStroke ?? opts.roughness > 0) drawOne()
}

/** Rough rectangle — four jittered edges, optional double-stroke. */
export function roughRect(
  path: Path2D,
  x: number,
  y: number,
  width: number,
  height: number,
  rng: () => number,
  opts: RoughOpts,
): void {
  const x2 = x + width
  const y2 = y + height
  roughLine(path, x, y, x2, y, rng, opts)
  roughLine(path, x2, y, x2, y2, rng, opts)
  roughLine(path, x2, y2, x, y2, rng, opts)
  roughLine(path, x, y2, x, y, rng, opts)
}

/** Rough ellipse — sample N points around the curve, perturb each,
 *  and stitch with Bezier segments. Not a true ellipse but the
 *  reader's eye takes it as one, which is the point. */
export function roughEllipse(
  path: Path2D,
  cx: number,
  cy: number,
  rx: number,
  ry: number,
  rng: () => number,
  opts: RoughOpts,
): void {
  const off = offsetFor(opts.roughness, Math.max(rx, ry))
  const steps = 14 + (opts.roughness === 2 ? 8 : 0)

  const drawOne = () => {
    // Start at a slight offset so double-strokes don't overlap
    // perfectly.
    const phase = rng() * 0.2
    const points: Array<[number, number]> = []
    for (let i = 0; i < steps; i++) {
      const t = (i / steps) * Math.PI * 2 + phase
      const x = cx + Math.cos(t) * rx
      const y = cy + Math.sin(t) * ry
      points.push(perturb(x, y, off, rng))
    }
    // Close with a Bezier loop — taking (p[i-1], p[i], p[i+1]) as
    // a control chain gives smooth sides with the jitter baked in.
    path.moveTo(points[0][0], points[0][1])
    for (let i = 0; i < points.length; i++) {
      const p1 = points[(i + 1) % points.length]
      const mx = (points[i][0] + p1[0]) / 2
      const my = (points[i][1] + p1[1]) / 2
      path.quadraticCurveTo(points[i][0], points[i][1], mx, my)
    }
    path.closePath()
  }

  drawOne()
  if (opts.doubleStroke ?? opts.roughness > 0) drawOne()
}

/** Normalise a user-provided roughness value into our 0/1/2 enum. */
export function clampRoughness(n: number): RoughLevel {
  if (n <= 0) return 0
  if (n >= 2) return 2
  return 1
}
