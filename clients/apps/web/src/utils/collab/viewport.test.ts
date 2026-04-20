import { describe, expect, it } from 'vitest'

import {
  MAX_SCALE,
  MIN_SCALE,
  clampScale,
  makeViewport,
  panByScreen,
  screenToWorld,
  visibleBounds,
  worldToScreen,
  zoomAt,
} from './viewport'

describe('viewport', () => {
  it('makeViewport fills sensible defaults', () => {
    const vp = makeViewport()
    expect(vp.scale).toBe(1)
    expect(vp.scrollX).toBe(0)
    expect(vp.scrollY).toBe(0)
  })

  it('screen/world are inverses at scale 1 with no scroll', () => {
    const vp = makeViewport()
    const w = screenToWorld(vp, 42, 99)
    expect(w).toEqual({ x: 42, y: 99 })
    const s = worldToScreen(vp, w.x, w.y)
    expect(s).toEqual({ x: 42, y: 99 })
  })

  it('screen/world are inverses with scale and scroll', () => {
    const vp = makeViewport({ scale: 2, scrollX: 100, scrollY: 50 })
    const w = screenToWorld(vp, 60, 80)
    expect(w).toEqual({ x: 100 + 60 / 2, y: 50 + 80 / 2 })
    const s = worldToScreen(vp, w.x, w.y)
    expect(s).toEqual({ x: 60, y: 80 })
  })

  it('clampScale enforces the 10%–3000% range', () => {
    expect(clampScale(0.001)).toBe(MIN_SCALE)
    expect(clampScale(100)).toBe(MAX_SCALE)
    expect(clampScale(1.5)).toBe(1.5)
  })

  it('clampScale handles non-finite input by falling back to 1', () => {
    // NaN and ±Infinity all fail Number.isFinite; the fallback is 1
    // (the sensible default) rather than "the bound closest to
    // infinity" because callers would rather see a clean default than
    // a silent max-zoom on a garbage input.
    expect(clampScale(NaN)).toBe(1)
    expect(clampScale(Infinity)).toBe(1)
    expect(clampScale(-Infinity)).toBe(1)
  })

  it('zoomAt keeps the world point under the cursor fixed', () => {
    const vp = makeViewport({ scale: 1 })
    const cursorX = 200
    const cursorY = 150
    const worldBefore = screenToWorld(vp, cursorX, cursorY)

    const zoomed = zoomAt(vp, cursorX, cursorY, 2)
    const worldAfter = screenToWorld(zoomed, cursorX, cursorY)

    expect(worldAfter.x).toBeCloseTo(worldBefore.x, 10)
    expect(worldAfter.y).toBeCloseTo(worldBefore.y, 10)
    expect(zoomed.scale).toBe(2)
  })

  it('zoomAt clamps extreme zoom requests', () => {
    const vp = makeViewport()
    expect(zoomAt(vp, 0, 0, 100).scale).toBe(MAX_SCALE)
    expect(zoomAt(vp, 0, 0, 0.0001).scale).toBe(MIN_SCALE)
  })

  it('panByScreen moves the world opposite the drag', () => {
    const vp = makeViewport({ scrollX: 10, scrollY: 20, scale: 2 })
    const panned = panByScreen(vp, 100, 50)
    // Drag right+down 100/50 screen px at scale 2 should SHIFT
    // the scrollOrigin LEFT by 50 world and UP by 25.
    expect(panned.scrollX).toBe(10 - 50)
    expect(panned.scrollY).toBe(20 - 25)
    expect(panned.scale).toBe(2)
  })

  it('visibleBounds scales with the zoom', () => {
    const vp = makeViewport({ scrollX: 5, scrollY: 7, scale: 2 })
    const bounds = visibleBounds(vp, 800, 600)
    expect(bounds).toEqual({ x: 5, y: 7, width: 400, height: 300 })
  })
})
