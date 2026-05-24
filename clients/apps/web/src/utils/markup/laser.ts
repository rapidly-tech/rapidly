/**
 * Laser pointer trail — a transient cursor-highlight peers share to
 * draw attention to a spot without leaving anything persistent on
 * the canvas.
 *
 * This module owns the **state**: a sliding window of recent cursor
 * samples with timestamps, pruned to a rolling TTL. The state is
 * broadcast via ``PresenceSource`` on the wire and painted by
 * ``laser-overlay.ts`` on the receiving side.
 *
 * Design
 * ------
 *  - Pure: no timers, no DOM. Callers drive ``push`` from their own
 *    pointer-move handler and ``snapshot`` from the renderer.
 *  - Timestamps stay on each sample so ``snapshot`` can compute an
 *    exact fade even when frames drop (sample rate isn't stable
 *    enough to derive age from array index).
 *  - ``maxPoints`` caps memory + wire size so a long dwell doesn't
 *    grow the trail unboundedly.
 */

/** One sample of the laser trail. ``t`` is ``performance.now()`` on
 *  the emitting client — the receiving client normalises against its
 *  own clock when computing fade, so drift is limited to the render
 *  frame it arrives in. */
export interface LaserPoint {
  x: number
  y: number
  t: number
}

export interface LaserState {
  points: readonly LaserPoint[]
}

export interface LaserController {
  /** Record a new sample at ``now`` and prune anything older than
   *  the TTL. Returns the updated snapshot so the caller can
   *  broadcast it via presence without calling ``snapshot`` twice. */
  push(x: number, y: number, now: number): LaserState
  /** Snapshot pruned to ``now`` — the trail without anything older
   *  than the TTL. Returned array is a new list; safe to hand to
   *  React render. */
  snapshot(now: number): LaserState
  /** Drop every sample. Used when the user flips laser mode off or
   *  cancels the gesture. */
  clear(): void
}

export interface LaserOptions {
  /** How long a point survives in the trail. Default 900 ms — long
   *  enough to paint a visible trail, short enough that it never
   *  feels like the trail is ""stuck"" behind the cursor. */
  ttlMs?: number
  /** Hard cap on trail length to bound memory + wire payload. */
  maxPoints?: number
}

const DEFAULT_TTL_MS = 900
const DEFAULT_MAX_POINTS = 40

/** Build a fresh laser-state controller. State lives on the closure
 *  — consumers own lifecycle by constructing one per session / tool
 *  mount. */
export function createLaserState(options: LaserOptions = {}): LaserController {
  const ttl = options.ttlMs ?? DEFAULT_TTL_MS
  const cap = options.maxPoints ?? DEFAULT_MAX_POINTS
  let points: LaserPoint[] = []

  const prune = (now: number): void => {
    // Drop points older than TTL — binary search would be faster but
    // with a 40-point cap, a linear splice is fine.
    const cutoff = now - ttl
    while (points.length > 0 && points[0].t < cutoff) points.shift()
    while (points.length > cap) points.shift()
  }

  return {
    push(x, y, now) {
      points.push({ x, y, t: now })
      prune(now)
      return { points: points.slice() }
    },
    snapshot(now) {
      prune(now)
      return { points: points.slice() }
    },
    clear() {
      points = []
    },
  }
}

/** Pure age → alpha curve. Younger = more opaque. Used by the
 *  overlay + tests to assert fade behaviour. */
export function ageToAlpha(
  ageMs: number,
  ttlMs: number = DEFAULT_TTL_MS,
): number {
  if (ageMs <= 0) return 1
  if (ageMs >= ttlMs) return 0
  // Ease-out-quad — reads as a smooth trail tail rather than a hard
  // linear fade.
  const t = ageMs / ttlMs
  return 1 - t * t
}
