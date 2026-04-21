/**
 * Pressure helpers for the freedraw (pen) tool.
 *
 * Browsers report pointer pressure inconsistently:
 *   - **Stylus / Apple Pencil / Surface Pen** — real 0..1 pressure.
 *   - **Mouse** — ``e.pressure`` is ``0`` on down, ``0.5`` on move (per
 *     spec, but some browsers return ``0`` always).
 *   - **Touch** — most phones report either ``0`` or ``0.5`` depending
 *     on the OS's force-touch capability + the user's gesture.
 *
 * When real pressure isn't available we **simulate** it from pointer
 * velocity — faster strokes produce thinner ink, slower strokes
 * thicker. That's the pressure curve drawing tablets have trained
 * users to expect for decades and it gives a mouse or capacitive
 * touch surface a credible analog feel.
 *
 * The functions here are pure so the freedraw tool (and future shape
 * tools that want a pressure-like modulation) can share them, and so
 * tests don't need a DOM pointer event.
 */

export interface PressureSample {
  x: number
  y: number
  /** ``performance.now()`` on the sample; the velocity calc divides
   *  pixel delta by the time delta so this has to be monotonic + in
   *  ms. */
  t: number
}

/** Read the reported pressure off a PointerEvent-like object. Returns
 *  ``null`` when the device didn't report useful pressure (mouse + most
 *  touch inputs). Callers simulate in that case. */
export function readReportedPressure(event: {
  pointerType?: string
  pressure?: number
}): number | null {
  // Only trust pressure from pen-type pointers — mouse + touch readings
  // are unreliable across browsers. A stylus that happens to report 0
  // (the spec value for a non-button contact) still returns 0 here; the
  // tool should treat that as ""no signal"" and simulate.
  if (event.pointerType !== 'pen') return null
  const p = event.pressure
  if (typeof p !== 'number' || !Number.isFinite(p) || p <= 0) return null
  return Math.min(1, Math.max(0, p))
}

export interface SimulateOptions {
  /** Pressure at or below slow velocity. Default 0.9 — thick, slow
   *  strokes look confident. */
  slowPressure?: number
  /** Pressure at or above fast velocity. Default 0.2 — thin, quick
   *  lines feel like pen on paper. */
  fastPressure?: number
  /** Velocity (px/ms) at which the simulated pressure reaches
   *  ``fastPressure``. Default 2 px/ms — roughly a brisk scribble. */
  fastVelocityPxPerMs?: number
}

const DEFAULT_SLOW = 0.9
const DEFAULT_FAST = 0.2
const DEFAULT_FAST_VELOCITY = 2

/** Velocity → pressure curve. Linear falloff between slow and fast
 *  end-points; clamped to the [fast, slow] band so a dwell on a
 *  single point doesn't produce pressure > 1. */
export function simulatePressureFromVelocity(
  prev: PressureSample,
  curr: PressureSample,
  options: SimulateOptions = {},
): number {
  const slow = options.slowPressure ?? DEFAULT_SLOW
  const fast = options.fastPressure ?? DEFAULT_FAST
  const fastV = options.fastVelocityPxPerMs ?? DEFAULT_FAST_VELOCITY
  const dt = curr.t - prev.t
  if (dt <= 0) return slow
  const distance = Math.hypot(curr.x - prev.x, curr.y - prev.y)
  const velocity = distance / dt
  if (velocity <= 0) return slow
  if (velocity >= fastV) return fast
  // Linear interp between slow and fast endpoints.
  const t = velocity / fastV
  return slow + (fast - slow) * t
}

/** Exponential moving average so a single fast micro-jitter doesn't
 *  produce a one-sample-wide ink thinning. ``alpha`` is the weight of
 *  the new sample — lower values = more smoothing. Default 0.4 is a
 *  good balance between responsiveness and calligraphic fluidity. */
export function smoothPressure(
  current: number,
  target: number,
  alpha: number = 0.4,
): number {
  const clamped = Math.min(1, Math.max(0, alpha))
  return current * (1 - clamped) + target * clamped
}
