import { describe, expect, it } from 'vitest'

import { parseXYChart, xyChartToElements } from './mermaid-xychart'

describe('parseXYChart', () => {
  it('returns null when the source is not an xychart', () => {
    expect(parseXYChart('flowchart TD\nA --> B')).toBeNull()
    expect(parseXYChart('')).toBeNull()
  })

  it('accepts both xychart and xychart-beta headers', () => {
    expect(parseXYChart('xychart\nbar [1]')).not.toBeNull()
    expect(parseXYChart('xychart-beta\nbar [1]')).not.toBeNull()
  })

  it('parses title with or without quotes', () => {
    expect(parseXYChart('xychart-beta\ntitle Foo')!.title).toBe('Foo')
    expect(parseXYChart('xychart-beta\ntitle "Foo Bar"')!.title).toBe('Foo Bar')
  })

  it('captures x-axis category labels', () => {
    const c = parseXYChart('xychart-beta\nx-axis [jan, feb, mar]')!
    expect(c.xLabels).toEqual(['jan', 'feb', 'mar'])
  })

  it('captures y-axis label + range', () => {
    const c = parseXYChart('xychart-beta\ny-axis "Revenue" 0 --> 100')!
    expect(c.yLabel).toBe('Revenue')
    expect(c.yMin).toBe(0)
    expect(c.yMax).toBe(100)
  })

  it('accepts y-axis range without a label', () => {
    const c = parseXYChart('xychart-beta\ny-axis -10 --> 50')!
    expect(c.yLabel).toBe('')
    expect(c.yMin).toBe(-10)
    expect(c.yMax).toBe(50)
  })

  it('captures bar + line series', () => {
    const c = parseXYChart(`xychart-beta
      bar [1, 2, 3]
      line [4, 5, 6]`)!
    expect(c.series).toHaveLength(2)
    expect(c.series[0]).toEqual({ kind: 'bar', values: [1, 2, 3] })
    expect(c.series[1]).toEqual({ kind: 'line', values: [4, 5, 6] })
  })

  it('infers a y-range from data when none is declared', () => {
    const c = parseXYChart('xychart-beta\nbar [10, 20, 30]')!
    expect(c.yMin).toBe(0)
    expect(c.yMax).toBeGreaterThanOrEqual(30)
  })

  it('skips comments + tolerates trailing comments', () => {
    const c = parseXYChart(`xychart-beta
      %% intro
      bar [1, 2, 3] %% trailing`)!
    expect(c.series).toHaveLength(1)
  })
})

describe('xyChartToElements', () => {
  it('emits axes + per-bar rect for a bar series', () => {
    const c = parseXYChart(`xychart-beta
      title T
      x-axis [a, b, c]
      y-axis 0 --> 10
      bar [3, 5, 7]`)!
    const els = xyChartToElements(c)
    expect(els.filter((e) => e.type === 'line').length).toBeGreaterThanOrEqual(
      2,
    ) // x + y axes
    const bars = els.filter((e) => e.type === 'rect')
    expect(bars).toHaveLength(3)
  })

  it('emits a line segment per adjacent pair for a line series', () => {
    const c = parseXYChart(`xychart-beta
      x-axis [a, b, c, d]
      y-axis 0 --> 10
      line [1, 2, 3, 4]`)!
    const els = xyChartToElements(c)
    // 2 axis lines + 3 segments = 5 line elements.
    expect(els.filter((e) => e.type === 'line')).toHaveLength(5)
  })

  it('positions a higher value lower on screen than a smaller value', () => {
    const c = parseXYChart(`xychart-beta
      x-axis [a, b]
      y-axis 0 --> 10
      bar [1, 9]`)!
    const els = xyChartToElements(c)
    const bars = els.filter((e) => e.type === 'rect') as Array<{
      y: number
      height: number
    }>
    expect(bars).toHaveLength(2)
    // The 9-value bar starts higher (smaller y) than the 1-value bar.
    expect(bars[1].y).toBeLessThan(bars[0].y)
    expect(bars[1].height).toBeGreaterThan(bars[0].height)
  })

  it('emits 5 y-axis tick labels', () => {
    const c = parseXYChart('xychart-beta\nbar [1, 2, 3]')!
    const els = xyChartToElements(c)
    const tickTexts = els.filter(
      (e) =>
        e.type === 'text' &&
        (e as unknown as { fontFamily: string }).fontFamily === 'mono',
    )
    expect(tickTexts).toHaveLength(5)
  })

  it('emits one x-axis label per category', () => {
    const c = parseXYChart('xychart-beta\nx-axis [a, b, c, d]\nbar [1,2,3,4]')!
    const els = xyChartToElements(c)
    const xLabels = els
      .filter((e) => e.type === 'text')
      .map((e) => (e as unknown as { text: string }).text)
    expect(
      xLabels.filter((t) => ['a', 'b', 'c', 'd'].includes(t)),
    ).toHaveLength(4)
  })

  it('respects originX / originY', () => {
    const c = parseXYChart('xychart-beta\nx-axis [a]\nbar [1]')!
    const els = xyChartToElements(c, { originX: 500, originY: 300 })
    const allXs = els.filter((e) => 'x' in e).map((e) => (e as { x: number }).x)
    expect(Math.min(...allXs)).toBeGreaterThanOrEqual(500)
  })

  it('produces deterministic output for a given input', () => {
    const a = xyChartToElements(
      parseXYChart('xychart-beta\nbar [1,2,3]\nline [3,2,1]')!,
    )
    const b = xyChartToElements(
      parseXYChart('xychart-beta\nbar [1,2,3]\nline [3,2,1]')!,
    )
    expect(JSON.stringify(a)).toBe(JSON.stringify(b))
  })
})
