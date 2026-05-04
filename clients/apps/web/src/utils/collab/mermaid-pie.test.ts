import { describe, expect, it } from 'vitest'

import { parsePie, pieToElements } from './mermaid-pie'

describe('parsePie', () => {
  it('returns null when the source is not a pie chart', () => {
    expect(parsePie('flowchart TD\nA --> B')).toBeNull()
    expect(parsePie('')).toBeNull()
    expect(parsePie('hello')).toBeNull()
  })

  it('parses the minimal case', () => {
    const d = parsePie(`pie
      "A" : 1
      "B" : 1`)!
    expect(d.title).toBe('')
    expect(d.showData).toBe(false)
    expect(d.slices).toEqual([
      { label: 'A', value: 1 },
      { label: 'B', value: 1 },
    ])
  })

  it('captures showData on the header', () => {
    const d = parsePie('pie showData\n"A" : 1')!
    expect(d.showData).toBe(true)
  })

  it('captures the same-line title form', () => {
    const d = parsePie('pie title My Chart\n"A" : 1')!
    expect(d.title).toBe('My Chart')
  })

  it('captures the standalone title form', () => {
    const d = parsePie(`pie
      title My Chart
      "A" : 1`)!
    expect(d.title).toBe('My Chart')
  })

  it('accepts unquoted slice labels', () => {
    const d = parsePie('pie\nApples : 5\nPears : 3')!
    expect(d.slices.map((s) => s.label)).toEqual(['Apples', 'Pears'])
  })

  it('parses fractional and zero values', () => {
    const d = parsePie('pie\n"A" : 0.5\n"B" : 0\n"C" : 99.99')!
    expect(d.slices.map((s) => s.value)).toEqual([0.5, 0, 99.99])
  })

  it('skips comments + tolerates trailing comments', () => {
    const d = parsePie(`pie
      %% header comment
      "A" : 1 %% trailing`)!
    expect(d.slices).toHaveLength(1)
  })

  it('ignores garbled lines', () => {
    const d = parsePie(`pie
      "A" : 1
      garbled
      "B" : 2`)!
    expect(d.slices).toHaveLength(2)
  })
})

describe('pieToElements', () => {
  it('emits an ellipse + radial dividers + per-slice legend rows', () => {
    const d = parsePie(`pie title T
      "A" : 1
      "B" : 1`)!
    const els = pieToElements(d)
    // 1 title + 1 circle + 2 dividers + 2 swatches + 2 labels = 8.
    expect(els.filter((e) => e.type === 'ellipse')).toHaveLength(1)
    const lines = els.filter((e) => e.type === 'line')
    expect(lines).toHaveLength(2)
    const rects = els.filter((e) => e.type === 'rect')
    expect(rects).toHaveLength(2) // legend swatches
    const texts = els.filter((e) => e.type === 'text')
    expect(texts.length).toBeGreaterThanOrEqual(3) // title + 2 legend labels
  })

  it('omits dividers when total is zero', () => {
    const d = parsePie('pie\n"A" : 0\n"B" : 0')!
    const els = pieToElements(d)
    expect(els.filter((e) => e.type === 'line')).toHaveLength(0)
    // Legend rows still render so the user sees the zero values.
    expect(els.filter((e) => e.type === 'rect')).toHaveLength(2)
  })

  it('shows percentages in legend labels', () => {
    const d = parsePie('pie\n"A" : 30\n"B" : 70')!
    const els = pieToElements(d)
    const texts = els
      .filter((e) => e.type === 'text')
      .map((e) => (e as unknown as { text: string }).text)
    expect(texts.some((t) => t.includes('A — 30 (30%)'))).toBe(true)
    expect(texts.some((t) => t.includes('B — 70 (70%)'))).toBe(true)
  })

  it('respects the originX / originY offset', () => {
    const d = parsePie('pie\n"A" : 1')!
    const els = pieToElements(d, { originX: 500, originY: 300 })
    const ellipse = els.find((e) => e.type === 'ellipse') as {
      x: number
      y: number
    }
    expect(ellipse.x).toBe(500)
    expect(ellipse.y).toBe(300)
  })

  it('produces deterministic layout for a given input', () => {
    const a = pieToElements(parsePie('pie\n"A" : 1\n"B" : 2')!)
    const b = pieToElements(parsePie('pie\n"A" : 1\n"B" : 2')!)
    expect(JSON.stringify(a)).toBe(JSON.stringify(b))
  })
})
