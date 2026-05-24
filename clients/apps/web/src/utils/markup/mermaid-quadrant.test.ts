import { describe, expect, it } from 'vitest'

import { parseQuadrantChart, quadrantChartToElements } from './mermaid-quadrant'

describe('parseQuadrantChart', () => {
  it('returns null when the source is not a quadrant chart', () => {
    expect(parseQuadrantChart('flowchart TD\nA --> B')).toBeNull()
    expect(parseQuadrantChart('')).toBeNull()
  })

  it('parses title + axis labels + quadrant labels + a point', () => {
    const c = parseQuadrantChart(`quadrantChart
      title Reach vs Effort
      x-axis Low Reach --> High Reach
      y-axis Low Effort --> High Effort
      quadrant-1 We should do
      quadrant-2 Maybe
      quadrant-3 Don't bother
      quadrant-4 Do it now
      Campaign A: [0.3, 0.6]`)!
    expect(c.title).toBe('Reach vs Effort')
    expect(c.xAxisStart).toBe('Low Reach')
    expect(c.xAxisEnd).toBe('High Reach')
    expect(c.yAxisStart).toBe('Low Effort')
    expect(c.yAxisEnd).toBe('High Effort')
    expect(c.quadrantLabels).toEqual([
      'We should do',
      'Maybe',
      "Don't bother",
      'Do it now',
    ])
    expect(c.points).toEqual([{ label: 'Campaign A', x: 0.3, y: 0.6 }])
  })

  it('accepts a single-endpoint axis label', () => {
    const c = parseQuadrantChart(`quadrantChart
      x-axis Reach
      y-axis Effort`)!
    expect(c.xAxisStart).toBe('Reach')
    expect(c.xAxisEnd).toBe('')
  })

  it('captures multiple data points', () => {
    const c = parseQuadrantChart(`quadrantChart
      A: [0.1, 0.1]
      B: [0.5, 0.5]
      C: [0.9, 0.9]`)!
    expect(c.points).toHaveLength(3)
    expect(c.points.map((p) => p.label)).toEqual(['A', 'B', 'C'])
  })

  it('skips comments + tolerates trailing comments', () => {
    const c = parseQuadrantChart(`quadrantChart
      %% intro
      A: [0.5, 0.5] %% trailing`)!
    expect(c.points).toHaveLength(1)
  })

  it('ignores garbled lines', () => {
    const c = parseQuadrantChart(`quadrantChart
      A: [0.5, 0.5]
      garbled+++
      B: [0.1, 0.9]`)!
    expect(c.points).toHaveLength(2)
  })
})

describe('quadrantChartToElements', () => {
  it('emits four quadrant rects + per-point ellipse', () => {
    const c = parseQuadrantChart(`quadrantChart
      A: [0.3, 0.6]
      B: [0.8, 0.2]`)!
    const els = quadrantChartToElements(c)
    expect(els.filter((e) => e.type === 'rect')).toHaveLength(4)
    expect(els.filter((e) => e.type === 'ellipse')).toHaveLength(2)
  })

  it('emits the title text when set', () => {
    const c = parseQuadrantChart('quadrantChart\ntitle Hello')!
    const els = quadrantChartToElements(c)
    const titles = els.filter(
      (e) =>
        e.type === 'text' &&
        (e as unknown as { text: string }).text === 'Hello',
    )
    expect(titles).toHaveLength(1)
  })

  it('renders quadrant labels in their cells', () => {
    const c = parseQuadrantChart(`quadrantChart
      quadrant-1 Q1
      quadrant-2 Q2
      quadrant-3 Q3
      quadrant-4 Q4`)!
    const els = quadrantChartToElements(c)
    const labels = els
      .filter((e) => e.type === 'text')
      .map((e) => (e as unknown as { text: string }).text)
    expect(labels).toContain('Q1')
    expect(labels).toContain('Q2')
    expect(labels).toContain('Q3')
    expect(labels).toContain('Q4')
  })

  it('inverts the y-axis so y=1 lands at the top', () => {
    const c = parseQuadrantChart(`quadrantChart
      Top: [0.5, 0.95]
      Bottom: [0.5, 0.05]`)!
    const els = quadrantChartToElements(c)
    const ellipses = els.filter((e) => e.type === 'ellipse') as Array<{
      y: number
    }>
    expect(ellipses[0].y).toBeLessThan(ellipses[1].y)
  })

  it('respects originX / originY', () => {
    const c = parseQuadrantChart('quadrantChart\nA: [0.5, 0.5]')!
    const els = quadrantChartToElements(c, { originX: 500, originY: 300 })
    const ellipse = els.find((e) => e.type === 'ellipse') as {
      x: number
      y: number
    }
    expect(ellipse.x).toBeGreaterThanOrEqual(500)
    expect(ellipse.y).toBeGreaterThanOrEqual(300)
  })

  it('produces deterministic output for a given input', () => {
    const a = quadrantChartToElements(
      parseQuadrantChart('quadrantChart\nA: [0.1, 0.2]\nB: [0.3, 0.4]')!,
    )
    const b = quadrantChartToElements(
      parseQuadrantChart('quadrantChart\nA: [0.1, 0.2]\nB: [0.3, 0.4]')!,
    )
    expect(JSON.stringify(a)).toBe(JSON.stringify(b))
  })
})
