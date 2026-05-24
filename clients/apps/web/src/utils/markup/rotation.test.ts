/**
 * Rotation handle math — pinned behaviour:
 *
 * - ``rotationHandlePosition`` lives ROTATION_HANDLE_OFFSET_PX / scale
 *   world units above the top edge, rotated around the centre.
 * - ``hitRotationHandle`` returns true within radius, false outside.
 * - ``angleFromCentre`` matches ``Math.atan2`` semantics (y grows down).
 * - ``snapAngleToIncrement`` rounds to 15° when shift is held.
 * - ``nextAngle`` adds the pointer-angle delta on top of the initial
 *   element angle.
 */

import { describe, expect, it } from 'vitest'

import {
  ROTATION_HANDLE_OFFSET_PX,
  ROTATION_SNAP_RAD,
  angleFromCentre,
  hitRotationHandle,
  nextAngle,
  rotationHandlePosition,
  snapAngleToIncrement,
} from './rotation'
import { makeViewport } from './viewport'

const baseEl = { x: 100, y: 100, width: 200, height: 100, angle: 0 }

describe('rotationHandlePosition', () => {
  it('lives above the top edge by the screen-px offset (in world units)', () => {
    const pos = rotationHandlePosition(baseEl, makeViewport({ scale: 1 }))
    // Centre x = 200; top edge y = 100; handle y = 100 - 24 = 76.
    expect(pos.x).toBe(200)
    expect(pos.y).toBe(100 - ROTATION_HANDLE_OFFSET_PX)
  })

  it('scales the offset by 1/scale so screen distance stays constant', () => {
    const pos = rotationHandlePosition(baseEl, makeViewport({ scale: 2 }))
    // 24 screen-px ÷ scale 2 = 12 world units above the top edge.
    expect(pos.y).toBe(100 - ROTATION_HANDLE_OFFSET_PX / 2)
  })

  it('rotates around the element centre when the element is rotated', () => {
    // 90° rotation: a point ""above"" the centre (cx, cy - h) rotates
    // to ""right of"" the centre (cx + h, cy) (with positive angle =
    // clockwise in canvas space → math y is inverted).
    const rotated = rotationHandlePosition(
      { ...baseEl, angle: Math.PI / 2 },
      makeViewport({ scale: 1 }),
    )
    // Centre = (200, 150). Pre-rotation handle at (200, 76).
    // Apply rotatePoint(200, 76, 200, 150, π/2): dx=0, dy=-74 →
    // x = 200 + 0*cos - (-74)*sin = 200 + 74 = 274; y = 150 + 0*sin + (-74)*cos = 150.
    expect(rotated.x).toBeCloseTo(274)
    expect(rotated.y).toBeCloseTo(150)
  })
})

describe('hitRotationHandle', () => {
  const vp = makeViewport({ scale: 1 })

  it('hits within the radius', () => {
    const w = rotationHandlePosition(baseEl, vp)
    // Convert world to screen: screen = (w - scroll) * scale; with
    // default vp scroll 0, scale 1 → screen == world.
    expect(hitRotationHandle(baseEl, vp, w.x, w.y)).toBe(true)
    expect(hitRotationHandle(baseEl, vp, w.x + 5, w.y)).toBe(true)
  })

  it('misses outside the radius', () => {
    const w = rotationHandlePosition(baseEl, vp)
    expect(hitRotationHandle(baseEl, vp, w.x + 50, w.y)).toBe(false)
  })

  it('respects a custom radius', () => {
    const w = rotationHandlePosition(baseEl, vp)
    expect(hitRotationHandle(baseEl, vp, w.x + 15, w.y, 20)).toBe(true)
    expect(hitRotationHandle(baseEl, vp, w.x + 15, w.y, 5)).toBe(false)
  })
})

describe('angleFromCentre', () => {
  it('matches atan2 semantics with y growing downward', () => {
    expect(angleFromCentre(0, 0, 1, 0)).toBeCloseTo(0)
    expect(angleFromCentre(0, 0, 0, 1)).toBeCloseTo(Math.PI / 2) // down → +π/2
    expect(angleFromCentre(0, 0, -1, 0)).toBeCloseTo(Math.PI)
    expect(angleFromCentre(0, 0, 0, -1)).toBeCloseTo(-Math.PI / 2) // up → -π/2
  })
})

describe('snapAngleToIncrement', () => {
  it('rounds to the nearest 15° when shift is held', () => {
    // 10° → 15°; 20° → 15°; 23° → 30°.
    expect(snapAngleToIncrement((10 * Math.PI) / 180, true)).toBeCloseTo(
      ROTATION_SNAP_RAD,
    )
    expect(snapAngleToIncrement((20 * Math.PI) / 180, true)).toBeCloseTo(
      ROTATION_SNAP_RAD,
    )
    expect(snapAngleToIncrement((23 * Math.PI) / 180, true)).toBeCloseTo(
      2 * ROTATION_SNAP_RAD,
    )
  })

  it('returns the angle unchanged when shift is off', () => {
    const a = (17 * Math.PI) / 180
    expect(snapAngleToIncrement(a, false)).toBe(a)
  })

  it('handles negative angles symmetrically', () => {
    expect(snapAngleToIncrement(-(20 * Math.PI) / 180, true)).toBeCloseTo(
      -ROTATION_SNAP_RAD,
    )
  })
})

describe('nextAngle', () => {
  it('adds the pointer-angle delta to the initial element angle', () => {
    // Initial pointer at 0 rad, current at π/4, element starts at π/2.
    // Result = π/2 + π/4 = 3π/4.
    expect(nextAngle(0, Math.PI / 4, Math.PI / 2, false)).toBeCloseTo(
      (3 * Math.PI) / 4,
    )
  })

  it('snaps the result to 15° when shift is held', () => {
    // Delta of 17° from initial 0 → raw 17° → snaps to 15°.
    const result = nextAngle(0, (17 * Math.PI) / 180, 0, true)
    expect(result).toBeCloseTo(ROTATION_SNAP_RAD)
  })
})
