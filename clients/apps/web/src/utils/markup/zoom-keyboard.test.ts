/**
 * Keyboard zoom helpers — pinned behaviour:
 *
 * - In / out multiply the current scale by ``ZOOM_KEYBOARD_STEP``.
 * - Reset returns scale to ``ZOOM_RESET_SCALE`` (1.0).
 * - Anchor is the canvas mid-point so the centre of the visible
 *   region stays put.
 * - ``zoomDirectionForKey`` maps ``=``/``+``/``-``/``_``/``0`` and
 *   returns null for everything else.
 * - Scale clamps to the viewport's MIN/MAX.
 */

import { describe, expect, it } from 'vitest'

import { MAX_SCALE, MIN_SCALE, makeViewport } from './viewport'
import {
  ZOOM_KEYBOARD_STEP,
  ZOOM_RESET_SCALE,
  viewportForKeyboardZoom,
  zoomDirectionForKey,
} from './zoom-keyboard'

describe('viewportForKeyboardZoom', () => {
  const W = 800
  const H = 600

  it('multiplies the scale by the step on zoom-in', () => {
    const vp = makeViewport({ scale: 1 })
    const next = viewportForKeyboardZoom(vp, 'in', W, H)
    expect(next.scale).toBeCloseTo(ZOOM_KEYBOARD_STEP)
  })

  it('divides the scale by the step on zoom-out', () => {
    const vp = makeViewport({ scale: 1 })
    const next = viewportForKeyboardZoom(vp, 'out', W, H)
    expect(next.scale).toBeCloseTo(1 / ZOOM_KEYBOARD_STEP)
  })

  it('resets the scale to ZOOM_RESET_SCALE', () => {
    const vp = makeViewport({ scale: 4 })
    const next = viewportForKeyboardZoom(vp, 'reset', W, H)
    expect(next.scale).toBe(ZOOM_RESET_SCALE)
  })

  it('keeps the canvas-centre world point fixed under zoom-in', () => {
    const vp = makeViewport({ scale: 1, scrollX: 0, scrollY: 0 })
    // Centre at screen (W/2, H/2) maps to world (W/2, H/2) at scale 1.
    const before = {
      x: vp.scrollX + W / (2 * vp.scale),
      y: vp.scrollY + H / (2 * vp.scale),
    }
    const next = viewportForKeyboardZoom(vp, 'in', W, H)
    const after = {
      x: next.scrollX + W / (2 * next.scale),
      y: next.scrollY + H / (2 * next.scale),
    }
    expect(after.x).toBeCloseTo(before.x)
    expect(after.y).toBeCloseTo(before.y)
  })

  it('clamps scale to MAX_SCALE on zoom-in', () => {
    const vp = makeViewport({ scale: MAX_SCALE })
    const next = viewportForKeyboardZoom(vp, 'in', W, H)
    expect(next.scale).toBe(MAX_SCALE)
  })

  it('clamps scale to MIN_SCALE on zoom-out', () => {
    const vp = makeViewport({ scale: MIN_SCALE })
    const next = viewportForKeyboardZoom(vp, 'out', W, H)
    expect(next.scale).toBe(MIN_SCALE)
  })
})

describe('zoomDirectionForKey', () => {
  it('maps the zoom-in keys', () => {
    expect(zoomDirectionForKey('=')).toBe('in')
    expect(zoomDirectionForKey('+')).toBe('in')
  })

  it('maps the zoom-out keys', () => {
    expect(zoomDirectionForKey('-')).toBe('out')
    expect(zoomDirectionForKey('_')).toBe('out')
  })

  it('maps reset to 0', () => {
    expect(zoomDirectionForKey('0')).toBe('reset')
  })

  it('returns null for non-zoom keys', () => {
    expect(zoomDirectionForKey('1')).toBeNull()
    expect(zoomDirectionForKey('z')).toBeNull()
    expect(zoomDirectionForKey(' ')).toBeNull()
  })
})
