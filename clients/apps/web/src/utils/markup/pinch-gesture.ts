/**
 * Pinch-to-zoom + two-finger pan gesture helper.
 *
 * Pointer events (not ``touchstart`` / ``touchmove``) so the same
 * code path works for trackpad multi-touch, touchscreens, and pen +
 * finger combinations. The gesture is a **pure state machine**: you
 * feed it pointerdown / pointermove / pointerup events and it emits
 * one ``PinchPanUpdate`` per move once two pointers are active.
 *
 * Semantics
 * ---------
 *   - Active only while ≥ 2 pointers are down. A third pointer
 *     joining is ignored (we keep tracking the first two) so a stray
 *     palm contact doesn't break the pinch.
 *   - ``scaleFactor`` is the **multiplier** vs. the previous frame —
 *     cumulative scale lives on the caller's viewport, not here.
 *     Keeps this module safe to drop into any renderer without
 *     knowing the min / max scale bounds.
 *   - ``panDeltaScreen{X,Y}`` is the midpoint delta in screen
 *     coords. Callers who want world-space pan divide by the current
 *     scale themselves.
 *   - ``center{X,Y}`` is the current pinch midpoint — the right
 *     anchor for ``zoomAt`` so the pinch focal point stays fixed
 *     under the fingers.
 *
 * The module is DOM-agnostic: it takes plain ``{id, x, y}`` triples.
 * The demo / ``useCollabRoom`` hook pulls those off ``PointerEvent``
 * before calling in. That keeps unit tests trivial — no jsdom event
 * construction needed.
 */

export interface PinchPointer {
  id: number
  x: number
  y: number
}

export interface PinchPanUpdate {
  /** Multiplicative scale change since the previous ``onPointerMove``
   *  (or since gesture start if this is the first move). 1 = no
   *  change; 2 = fingers pulled twice as far apart. Always > 0. */
  scaleFactor: number
  /** Pan delta in screen coords since the previous move. */
  panDeltaScreenX: number
  panDeltaScreenY: number
  /** Current pinch midpoint in screen coords. */
  centerScreenX: number
  centerScreenY: number
}

export interface PinchPanGesture {
  /** Register a new pointer. Activates the gesture once two are
   *  tracked. */
  onPointerDown(p: PinchPointer): void
  /** Update an existing pointer. Returns a ``PinchPanUpdate`` when
   *  the gesture is active and this move belongs to one of the
   *  tracked pointers; ``null`` otherwise. */
  onPointerMove(p: PinchPointer): PinchPanUpdate | null
  /** Deregister a pointer. The gesture deactivates on the first
   *  drop — leftover single-pointer interaction is for the tool
   *  below to handle. */
  onPointerUp(id: number): void
  /** True iff two tracked pointers are down right now. */
  active(): boolean
  /** Drop all tracked pointers. Use in ``onCancel`` paths (e.g. tool
   *  switch mid-gesture). */
  reset(): void
}

export function createPinchPanGesture(): PinchPanGesture {
  // We keep at most two pointers. A Map would also work but an array
  // preserves order-of-arrival which matters for stable mid-gesture
  // third-finger handling.
  let tracked: PinchPointer[] = []
  let lastCenter: { x: number; y: number } | null = null
  let lastDistance = 0

  const computeCenter = (
    a: PinchPointer,
    b: PinchPointer,
  ): { x: number; y: number } => ({
    x: (a.x + b.x) / 2,
    y: (a.y + b.y) / 2,
  })

  const computeDistance = (a: PinchPointer, b: PinchPointer): number => {
    const dx = b.x - a.x
    const dy = b.y - a.y
    return Math.hypot(dx, dy)
  }

  const trackedIndex = (id: number): number =>
    tracked.findIndex((p) => p.id === id)

  return {
    onPointerDown(p) {
      // Already tracking two? Ignore a third. Already tracking this
      // id? Replace (shouldn't happen normally but keeps state sane
      // if the host re-fires pointerdown).
      const existing = trackedIndex(p.id)
      if (existing !== -1) {
        tracked[existing] = { ...p }
        return
      }
      if (tracked.length >= 2) return
      tracked.push({ ...p })
      if (tracked.length === 2) {
        lastCenter = computeCenter(tracked[0], tracked[1])
        lastDistance = computeDistance(tracked[0], tracked[1])
      }
    },
    onPointerMove(p) {
      const idx = trackedIndex(p.id)
      if (idx === -1) return null
      tracked[idx] = { ...p }
      if (tracked.length !== 2 || !lastCenter) return null

      const [a, b] = tracked
      const newCenter = computeCenter(a, b)
      const newDistance = computeDistance(a, b)

      // Scale factor vs. previous frame. Guard against a zero-distance
      // denominator (both pointers at the same pixel — theoretical
      // but cheap to cover).
      const scaleFactor =
        lastDistance > 0 && newDistance > 0 ? newDistance / lastDistance : 1
      const update: PinchPanUpdate = {
        scaleFactor,
        panDeltaScreenX: newCenter.x - lastCenter.x,
        panDeltaScreenY: newCenter.y - lastCenter.y,
        centerScreenX: newCenter.x,
        centerScreenY: newCenter.y,
      }
      lastCenter = newCenter
      lastDistance = newDistance
      return update
    },
    onPointerUp(id) {
      const idx = trackedIndex(id)
      if (idx === -1) return
      tracked.splice(idx, 1)
      // Any pointer leaving ends the gesture entirely — don't hand
      // off to a one-finger mode here, the tool below already
      // handles single-pointer interaction.
      lastCenter = null
      lastDistance = 0
    },
    active() {
      return tracked.length === 2
    },
    reset() {
      tracked = []
      lastCenter = null
      lastDistance = 0
    },
  }
}
