import { describe, expect, it, vi } from 'vitest'

import { paintFill, type FillTarget } from './fills'

/** Minimal fake CanvasRenderingContext2D — records every method call
 *  + property assignment so tests can assert on the order and shape of
 *  the painter's output without needing a real canvas. */
function makeCtx() {
  const calls: string[] = []
  const props: Record<string, unknown> = {}
  const proxy = new Proxy(
    {},
    {
      get(_target, prop: string) {
        if (prop in props) return props[prop]
        return (...args: unknown[]) => {
          calls.push(`${prop}(${args.length})`)
        }
      },
      set(_target, prop: string, value) {
        props[prop] = value
        return true
      },
    },
  )
  return { ctx: proxy as unknown as CanvasRenderingContext2D, calls, props }
}

const path = {} as Path2D

const base: FillTarget = {
  fillColor: '#ff0000',
  fillStyle: 'solid',
  strokeWidth: 2,
}

describe('paintFill', () => {
  it('no-ops when fillColor is transparent', () => {
    const { ctx, calls } = makeCtx()
    paintFill(
      ctx,
      path,
      { ...base, fillColor: 'transparent' },
      { width: 100, height: 50 },
    )
    expect(calls).toEqual([])
  })

  it('no-ops when fillStyle is none', () => {
    const { ctx, calls } = makeCtx()
    paintFill(
      ctx,
      path,
      { ...base, fillStyle: 'none' },
      { width: 100, height: 50 },
    )
    expect(calls).toEqual([])
  })

  it('does a single fill() for solid', () => {
    const { ctx, calls, props } = makeCtx()
    paintFill(ctx, path, base, { width: 100, height: 50 })
    expect(props.fillStyle).toBe('#ff0000')
    expect(calls.filter((c) => c.startsWith('fill('))).toHaveLength(1)
    // Solid does not need clip()/save() — it's the cheap path.
    expect(calls).not.toContain('clip(1)')
  })

  it('clips and emits stroke calls for hatch', () => {
    const { ctx, calls } = makeCtx()
    paintFill(
      ctx,
      path,
      { ...base, fillStyle: 'hatch' },
      { width: 80, height: 80, spacing: 10 },
    )
    expect(calls.filter((c) => c === 'clip(1)')).toHaveLength(1)
    // 45° hatch covers ±diag in 10-unit steps; with diag ≈ 113 we expect
    // (113 * 2 / 10) + 1 ≈ 23 strokes plus the moveTo/lineTo/beginPath
    // pairs. Lower bound is enough to prove lines were emitted.
    const strokeCalls = calls.filter((c) => c === 'stroke(0)')
    expect(strokeCalls.length).toBeGreaterThan(10)
  })

  it('cross-hatch emits roughly twice the strokes of hatch', () => {
    const single = makeCtx()
    paintFill(
      single.ctx,
      path,
      { ...base, fillStyle: 'hatch' },
      { width: 80, height: 80, spacing: 10 },
    )
    const cross = makeCtx()
    paintFill(
      cross.ctx,
      path,
      { ...base, fillStyle: 'cross-hatch' },
      { width: 80, height: 80, spacing: 10 },
    )
    const singleStrokes = single.calls.filter((c) => c === 'stroke(0)').length
    const crossStrokes = cross.calls.filter((c) => c === 'stroke(0)').length
    expect(crossStrokes).toBeGreaterThanOrEqual(singleStrokes * 2 - 2)
    expect(crossStrokes).toBeLessThanOrEqual(singleStrokes * 2 + 2)
  })

  it('dots emits arc + fill per dot, gridded by spacing', () => {
    const { ctx, calls } = makeCtx()
    paintFill(
      ctx,
      path,
      { ...base, fillStyle: 'dots' },
      { width: 30, height: 30, spacing: 10 },
    )
    // 30 / 10 = 3 columns × 3 rows = 9 dots
    const arcCalls = calls.filter((c) => c.startsWith('arc('))
    expect(arcCalls).toHaveLength(9)
    // Each dot should fill (no path arg → fill())
    const fillCalls = calls.filter((c) => c === 'fill(0)')
    expect(fillCalls).toHaveLength(9)
  })

  it('uses fillColor as the line/dot colour, not the stroke palette', () => {
    const { ctx, props } = makeCtx()
    paintFill(
      ctx,
      path,
      { ...base, fillColor: '#abcdef', fillStyle: 'hatch' },
      { width: 50, height: 50 },
    )
    expect(props.strokeStyle).toBe('#abcdef')
  })

  it('balances every save() with a restore()', () => {
    for (const style of ['hatch', 'cross-hatch', 'dots'] as const) {
      const { ctx, calls } = makeCtx()
      paintFill(
        ctx,
        path,
        { ...base, fillStyle: style },
        { width: 40, height: 40 },
      )
      const saves = calls.filter((c) => c === 'save(0)').length
      const restores = calls.filter((c) => c === 'restore(0)').length
      expect(restores, `${style} balance`).toBe(saves)
    }
  })

  it('keeps the work bounded for very large shapes', () => {
    // Edge case: a shape so large the diagonal sweep would explode if
    // we forgot a sane upper bound. Using a 4096-wide rect with 8-unit
    // spacing should cap at a few hundred strokes — not millions.
    const { ctx, calls } = makeCtx()
    const start = performance.now()
    paintFill(
      ctx,
      path,
      { ...base, fillStyle: 'cross-hatch' },
      { width: 4096, height: 64, spacing: 8 },
    )
    const elapsed = performance.now() - start
    expect(elapsed).toBeLessThan(50) // generous; should be sub-ms
    const strokes = calls.filter((c) => c === 'stroke(0)').length
    expect(strokes).toBeLessThan(2500)
    vi.useRealTimers()
  })
})
