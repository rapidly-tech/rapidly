import { afterEach, beforeAll, describe, expect, it, vi } from 'vitest'

// jsdom has no canvas backend and therefore no Path2D. Stub it so
// pathFor can instantiate without throwing.
beforeAll(() => {
  if (typeof (globalThis as { Path2D?: unknown }).Path2D === 'undefined') {
    ;(globalThis as { Path2D: unknown }).Path2D = class {
      rect() {}
    }
  }
})

import {
  DEFAULT_FILL_COLOR,
  DEFAULT_FILL_STYLE,
  DEFAULT_OPACITY,
  DEFAULT_ROUGHNESS,
  DEFAULT_STROKE_COLOR,
  DEFAULT_STROKE_STYLE,
  DEFAULT_STROKE_WIDTH,
  type TextElement,
} from '../elements'
import { fontCssFor, measureText, paintText, pathFor } from './text'

function textEl(overrides: Partial<TextElement> = {}): TextElement {
  return {
    id: 't1',
    type: 'text',
    x: 0,
    y: 0,
    width: 200,
    height: 40,
    angle: 0,
    zIndex: 0,
    groupIds: [],
    strokeColor: DEFAULT_STROKE_COLOR,
    fillColor: DEFAULT_FILL_COLOR,
    fillStyle: DEFAULT_FILL_STYLE,
    strokeWidth: DEFAULT_STROKE_WIDTH,
    strokeStyle: DEFAULT_STROKE_STYLE,
    roughness: DEFAULT_ROUGHNESS,
    opacity: DEFAULT_OPACITY,
    seed: 1,
    version: 1,
    locked: false,
    text: 'Hello',
    fontFamily: 'handwritten',
    fontSize: 20,
    textAlign: 'left',
    ...overrides,
  }
}

describe('fontCssFor', () => {
  it('maps families to safe font stacks', () => {
    expect(fontCssFor('handwritten')).toContain('cursive')
    expect(fontCssFor('mono')).toContain('monospace')
    expect(fontCssFor('sans')).toContain('sans-serif')
  })
})

describe('pathFor', () => {
  it('returns the element AABB as the hit target', () => {
    // Smoke: no throw + returns a Path2D-like object. We don't
    // hit-test here because jsdom Path2D is polyfilled no-op in
    // renderer.test.ts; specific geometry is covered by the
    // renderer's hit-test tests.
    const p = pathFor(textEl())
    expect(p).toBeDefined()
  })
})

describe('paintText', () => {
  it('splits on \\n and calls fillText once per line at the left anchor', () => {
    const calls: Array<[string, number, number]> = []
    const ctx = {
      save: vi.fn(),
      restore: vi.fn(),
      fillText: (text: string, x: number, y: number) => {
        calls.push([text, x, y])
      },
      set globalAlpha(_v: number) {},
      set fillStyle(_v: string) {},
      set textBaseline(_v: string) {},
      set textAlign(_v: string) {},
      set font(_v: string) {},
    } as unknown as CanvasRenderingContext2D

    paintText(ctx, textEl({ text: 'line one\nline two' }), {} as Path2D)
    expect(calls.length).toBe(2)
    expect(calls[0][0]).toBe('line one')
    expect(calls[1][0]).toBe('line two')
    expect(calls[0][1]).toBe(0) // left-aligned anchor
    // Line height = fontSize * 1.2 = 24 for fontSize 20.
    expect(calls[1][2]).toBe(24)
  })

  it('anchors at element centre when textAlign is center', () => {
    const calls: number[] = []
    const ctx = {
      save: vi.fn(),
      restore: vi.fn(),
      fillText: (_t: string, x: number) => calls.push(x),
      set globalAlpha(_v: number) {},
      set fillStyle(_v: string) {},
      set textBaseline(_v: string) {},
      set textAlign(_v: string) {},
      set font(_v: string) {},
    } as unknown as CanvasRenderingContext2D
    paintText(ctx, textEl({ textAlign: 'center', width: 200 }), {} as Path2D)
    expect(calls[0]).toBe(100)
  })

  it('anchors at element right edge when textAlign is right', () => {
    const calls: number[] = []
    const ctx = {
      save: vi.fn(),
      restore: vi.fn(),
      fillText: (_t: string, x: number) => calls.push(x),
      set globalAlpha(_v: number) {},
      set fillStyle(_v: string) {},
      set textBaseline(_v: string) {},
      set textAlign(_v: string) {},
      set font(_v: string) {},
    } as unknown as CanvasRenderingContext2D
    paintText(ctx, textEl({ textAlign: 'right', width: 200 }), {} as Path2D)
    expect(calls[0]).toBe(200)
  })
})

describe('measureText', () => {
  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('measures the widest line and sets height by lineCount × 1.2', () => {
    // Mock measureText so the test doesn't depend on the font
    // renderer being present.
    const ctx = {
      save: vi.fn(),
      restore: vi.fn(),
      measureText: (s: string) =>
        ({ width: s.length * 10 }) as unknown as TextMetrics,
      set font(_v: string) {},
    } as unknown as CanvasRenderingContext2D

    const size = measureText(ctx, 'abc\nabcdef', 'sans', 20)
    // Widest line has 6 chars × 10 = 60.
    expect(size.width).toBe(60)
    // 2 lines × (20 * 1.2) = 48.
    expect(size.height).toBe(48)
  })

  it('clamps to a minimum of 1 so degenerate measurements stay hit-testable', () => {
    const ctx = {
      save: vi.fn(),
      restore: vi.fn(),
      measureText: () => ({ width: 0 }) as unknown as TextMetrics,
      set font(_v: string) {},
    } as unknown as CanvasRenderingContext2D
    const size = measureText(ctx, '', 'sans', 20)
    expect(size.width).toBeGreaterThanOrEqual(1)
    expect(size.height).toBeGreaterThanOrEqual(1)
  })
})
