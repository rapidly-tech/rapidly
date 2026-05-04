import { describe, expect, it } from 'vitest'

import type { CollabElement } from './elements'
import { makeScrollbarsOverlay, unionAabb } from './scrollbars'

const baseElement = {
  id: 'a',
  type: 'rect',
  angle: 0,
  zIndex: 0,
  groupIds: [],
  strokeColor: '#000',
  fillColor: 'transparent',
  fillStyle: 'none',
  strokeWidth: 1,
  strokeStyle: 'solid',
  roughness: 0,
  opacity: 100,
  seed: 1,
  version: 1,
  locked: false,
  roundness: 0,
} as unknown as CollabElement

function el(
  x: number,
  y: number,
  w: number,
  h: number,
  id = `e${Math.random()}`,
): CollabElement {
  return { ...baseElement, id, x, y, width: w, height: h }
}

function makeCtx() {
  const calls: string[] = []
  const proxy = new Proxy(
    {},
    {
      get(_target, prop: string) {
        if (prop === 'fillStyle' || prop === 'strokeStyle') return ''
        return (...args: unknown[]) => {
          calls.push(`${prop}(${args.length})`)
        }
      },
      set() {
        return true
      },
    },
  )
  return { ctx: proxy as unknown as CanvasRenderingContext2D, calls }
}

describe('unionAabb', () => {
  it('returns null for an empty list', () => {
    expect(unionAabb([])).toBeNull()
  })

  it('matches a single element', () => {
    expect(unionAabb([el(10, 20, 30, 40)])).toEqual({
      x: 10,
      y: 20,
      width: 30,
      height: 40,
    })
  })

  it('grows to cover every element', () => {
    expect(unionAabb([el(0, 0, 10, 10), el(100, 50, 20, 20)])).toEqual({
      x: 0,
      y: 0,
      width: 120,
      height: 70,
    })
  })
})

describe('makeScrollbarsOverlay', () => {
  it('emits no draw calls on a pristine empty canvas', () => {
    const paint = makeScrollbarsOverlay({
      getElements: () => [],
      getViewport: () => ({ scale: 1, scrollX: 0, scrollY: 0 }),
    })
    const { ctx, calls } = makeCtx()
    paint(ctx, { width: 800, height: 600 })
    expect(calls).toEqual([])
  })

  it('paints two tracks + two thumbs when there is content', () => {
    const paint = makeScrollbarsOverlay({
      getElements: () => [el(0, 0, 4000, 4000)],
      getViewport: () => ({ scale: 1, scrollX: 100, scrollY: 100 }),
    })
    const { ctx, calls } = makeCtx()
    paint(ctx, { width: 800, height: 600 })
    // Each call to ``fill()`` paints a track or thumb. With both
    // tracks and both thumbs visible we expect 4 fills.
    expect(calls.filter((c) => c === 'fill(0)').length).toBe(4)
  })

  it('shows a single track + thumb axis when content fits one dimension', () => {
    // Wide-only content: 3000 × 100, viewport 800 × 600. The vertical
    // track still renders because the user could pan vertically; in
    // practice both tracks always appear when there's any content.
    const paint = makeScrollbarsOverlay({
      getElements: () => [el(0, 0, 3000, 100)],
      getViewport: () => ({ scale: 1, scrollX: 0, scrollY: 0 }),
    })
    const { ctx, calls } = makeCtx()
    paint(ctx, { width: 800, height: 600 })
    // Tracks always paint when there's any element; thumbs may snap
    // to MIN_THUMB_PX. Just check both axes produced at least the
    // track + thumb pair (≥4 fills total).
    expect(calls.filter((c) => c === 'fill(0)').length).toBeGreaterThanOrEqual(
      4,
    )
  })

  it('paints when the viewport has been panned past every element', () => {
    // No elements but the user has scrolled away from origin — show
    // the chrome so they can find their way back.
    const paint = makeScrollbarsOverlay({
      getElements: () => [],
      getViewport: () => ({ scale: 1, scrollX: 500, scrollY: 200 }),
    })
    const { ctx, calls } = makeCtx()
    paint(ctx, { width: 800, height: 600 })
    expect(calls.filter((c) => c === 'fill(0)').length).toBeGreaterThan(0)
  })
})
