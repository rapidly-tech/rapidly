/**
 * Smooth viewport transitions for the Collab v2 renderer.
 *
 * Presentation mode (Phase 24b) currently snaps the camera between
 * frames — a single ``setViewport`` call. Good for correctness, but
 * jarring in a talk where the audience loses context on each cut.
 * This module eases the camera between two viewports over a fixed
 * duration via ``requestAnimationFrame``.
 *
 * Kept as pure math + a thin rAF driver so the same helpers power
 * any future use-case (zoom-to-selection, double-tap-to-fit, etc.).
 */

import { clampScale, type Viewport } from './viewport'

/** Ease-in-out-cubic. Flat at both ends, steep in the middle — reads
 *  as a ""natural"" camera move rather than linear sweep. Pure: same
 *  input always produces same output. Exported so tests and future
 *  non-viewport animators can reuse it. */
export function easeInOutCubic(t: number): number {
  if (t <= 0) return 0
  if (t >= 1) return 1
  return t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2
}

/** Linearly interpolate two viewports and ease the parameter so the
 *  resulting motion matches the user's expectations. ``scale`` is
 *  clamped to the legal range on every frame — a mid-animation
 *  clamp hit otherwise produces a surprise jump. */
export function lerpViewport(
  from: Viewport,
  to: Viewport,
  tLinear: number,
): Viewport {
  const t = easeInOutCubic(tLinear)
  return {
    scale: clampScale(from.scale + (to.scale - from.scale) * t),
    scrollX: from.scrollX + (to.scrollX - from.scrollX) * t,
    scrollY: from.scrollY + (to.scrollY - from.scrollY) * t,
  }
}

export interface TransitionOptions {
  /** Total duration in ms. Default 400 — long enough to read as a
   *  deliberate move, short enough not to feel sluggish. */
  durationMs?: number
  /** Called with each intermediate viewport. Host copies into its
   *  own ``vpRef`` + re-renders. Always runs at least once (the final
   *  state) so a zero-duration call still settles correctly. */
  onFrame: (vp: Viewport) => void
  /** Called when the animation reaches its target or is cancelled.
   *  ``completed === true`` on natural finish, ``false`` if cancelled. */
  onDone?: (completed: boolean) => void
  /** Clock + RAF overrides — injected by tests. Defaults to
   *  ``performance.now`` / ``requestAnimationFrame``. */
  now?: () => number
  requestFrame?: (cb: (t: number) => void) => number
  cancelFrame?: (handle: number) => void
}

export interface TransitionHandle {
  /** Stop the animation early. Safe to call after completion — it's
   *  a no-op. Fires ``onDone(false)`` if still running. */
  cancel(): void
}

const DEFAULT_DURATION_MS = 400

/** Start an animated transition from ``from`` to ``to``. Returns a
 *  handle whose ``cancel`` stops the animation. The final frame is
 *  always the exact ``to`` viewport so there's no sub-pixel drift
 *  from accumulated easing. */
export function animateViewport(
  from: Viewport,
  to: Viewport,
  options: TransitionOptions,
): TransitionHandle {
  const duration = options.durationMs ?? DEFAULT_DURATION_MS
  const now = options.now ?? (() => performance.now())
  const raf = options.requestFrame ?? ((cb) => requestAnimationFrame(cb))
  const caf = options.cancelFrame ?? ((h: number) => cancelAnimationFrame(h))

  // Zero-duration → snap + fire once. Saves callers from having to
  // special-case identical-viewport calls in the keyboard handler.
  if (duration <= 0) {
    options.onFrame(to)
    options.onDone?.(true)
    return { cancel: () => {} }
  }

  const startTime = now()
  let cancelled = false
  let completed = false
  let handle = 0

  const tick = (): void => {
    if (cancelled) return
    const elapsed = now() - startTime
    const tLinear = Math.min(1, Math.max(0, elapsed / duration))
    if (tLinear >= 1) {
      completed = true
      options.onFrame(to)
      options.onDone?.(true)
      return
    }
    options.onFrame(lerpViewport(from, to, tLinear))
    handle = raf(tick)
  }

  handle = raf(tick)

  return {
    cancel() {
      if (completed || cancelled) return
      cancelled = true
      caf(handle)
      options.onDone?.(false)
    },
  }
}
