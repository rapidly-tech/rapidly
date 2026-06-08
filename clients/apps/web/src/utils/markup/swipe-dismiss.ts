/**
 * Swipe-down-to-dismiss gesture for bottom sheets.
 *
 * Tracks one vertical pointer and reports the running ``translateY``
 * (world offset from the gesture origin, clamped to ≥ 0 so sheets
 * don't peel upward). On release, decides **dismiss** vs. **snap
 * back** based on two independent thresholds:
 *
 *   - **Travel**: released past ``distanceThresholdPx`` — intent is
 *     clear, the user dragged far enough.
 *   - **Velocity**: released with ``|dy/dt| > velocityThresholdPxPerMs``
 *     even if travel was short — a quick flick.
 *
 * Either triggers dismiss. Matches iOS / Material gesture semantics.
 *
 * Why a pure controller
 * ---------------------
 * The sheet component owns the DOM (pointer listeners, transform
 * style, animated close). This module owns the math so it's unit-
 * testable without a DOM and reusable for any future sheet /
 * drawer / dialog that wants the same feel.
 */

export interface SwipeUpdate {
  /** Offset from gesture start, in screen pixels. Clamped to ≥ 0
   *  because we never want the sheet to rise past its mounted
   *  position. */
  translateY: number
}

export interface SwipeRelease {
  /** True when the gesture crossed either threshold on release. The
   *  sheet component animates to closed + calls ``onClose`` when
   *  this is ``true``, or snaps back to 0 when ``false``. */
  dismiss: boolean
  /** Final translateY at release — callers that animate the snap-
   *  back from the actual release position use this. */
  translateY: number
}

export interface SwipeDismissOptions {
  /** Travel threshold in screen pixels. Default 80 — roughly half a
   *  typical sheet header. */
  distanceThresholdPx?: number
  /** Velocity threshold in px / ms. Default 0.5 px/ms — a brisk
   *  flick. */
  velocityThresholdPxPerMs?: number
}

export interface SwipeDismissController {
  /** Start tracking a new gesture at ``(y, now)``. No-op when a
   *  gesture is already active. */
  onPointerDown(y: number, now: number): void
  /** Update with the latest sample. Returns the current translate
   *  when active, ``null`` before the first pointerdown. */
  onPointerMove(y: number, now: number): SwipeUpdate | null
  /** End the gesture. Returns whether to dismiss + the final
   *  translateY. */
  onPointerUp(y: number, now: number): SwipeRelease
  /** Reset state (e.g. sheet re-opened while a stale gesture
   *  lingered). Idempotent. */
  reset(): void
}

const DEFAULT_DISTANCE_PX = 80
const DEFAULT_VELOCITY_PX_PER_MS = 0.5

export function createSwipeDismiss(
  options: SwipeDismissOptions = {},
): SwipeDismissController {
  const distanceThreshold = options.distanceThresholdPx ?? DEFAULT_DISTANCE_PX
  const velocityThreshold =
    options.velocityThresholdPxPerMs ?? DEFAULT_VELOCITY_PX_PER_MS

  let startY: number | null = null
  let lastY = 0
  let lastT = 0
  let prevY = 0
  let prevT = 0

  const clampTranslate = (dy: number): number => Math.max(0, dy)

  return {
    onPointerDown(y, now) {
      if (startY !== null) return
      startY = y
      prevY = y
      prevT = now
      lastY = y
      lastT = now
    },
    onPointerMove(y, now) {
      if (startY === null) return null
      prevY = lastY
      prevT = lastT
      lastY = y
      lastT = now
      return { translateY: clampTranslate(y - startY) }
    },
    onPointerUp(y, now) {
      if (startY === null) return { dismiss: false, translateY: 0 }
      const travel = clampTranslate(y - startY)
      // Velocity uses the last two sample points (not gesture
      // average) so a slow hold followed by a quick release still
      // fires the flick path.
      const dt = now - prevT
      const velocity = dt > 0 ? (y - prevY) / dt : 0
      const dismiss = travel > distanceThreshold || velocity > velocityThreshold
      startY = null
      prevY = 0
      prevT = 0
      lastY = 0
      lastT = 0
      return { dismiss, translateY: travel }
    },
    reset() {
      startY = null
      prevY = 0
      prevT = 0
      lastY = 0
      lastT = 0
    },
  }
}
