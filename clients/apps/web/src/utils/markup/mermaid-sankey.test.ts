import { describe, expect, it } from 'vitest'

import { parseSankey, sankeyToElements } from './mermaid-sankey'

describe('parseSankey', () => {
  it('returns null when the source is not a sankey', () => {
    expect(parseSankey('flowchart TD\nA --> B')).toBeNull()
    expect(parseSankey('')).toBeNull()
  })

  it('accepts both sankey and sankey-beta headers', () => {
    expect(parseSankey('sankey\nA,B,1')).not.toBeNull()
    expect(parseSankey('sankey-beta\nA,B,1')).not.toBeNull()
  })

  it('parses a single link', () => {
    const d = parseSankey('sankey-beta\nA,B,10')!
    expect(d.links).toEqual([{ source: 'A', target: 'B', value: 10 }])
    const a = d.nodes.find((n) => n.id === 'A')!
    const b = d.nodes.find((n) => n.id === 'B')!
    expect(a.outflow).toBe(10)
    expect(a.inflow).toBe(0)
    expect(b.inflow).toBe(10)
    expect(b.outflow).toBe(0)
  })

  it('skips the optional CSV header row', () => {
    const d = parseSankey(`sankey-beta
      source,target,value
      A,B,5`)!
    expect(d.links).toHaveLength(1)
  })

  it('strips quotes from quoted CSV fields', () => {
    const d = parseSankey('sankey-beta\n"Customer A","Order","5"')!
    expect(d.links[0].source).toBe('Customer A')
    expect(d.links[0].target).toBe('Order')
    expect(d.links[0].value).toBe(5)
  })

  it('drops rows with non-numeric or non-positive values', () => {
    const d = parseSankey(`sankey-beta
      A,B,5
      A,B,abc
      A,B,-3
      A,B,0`)!
    expect(d.links).toHaveLength(1)
  })

  it('skips comments + tolerates trailing comments', () => {
    const d = parseSankey(`sankey-beta
      %% intro
      A,B,1 %% trailing`)!
    expect(d.links).toHaveLength(1)
  })

  it('assigns longest-path columns', () => {
    const d = parseSankey(`sankey-beta
      A,B,1
      B,C,1`)!
    const cols = new Map(d.nodes.map((n) => [n.id, n.column]))
    expect(cols.get('A')).toBe(0)
    expect(cols.get('B')).toBe(1)
    expect(cols.get('C')).toBe(2)
  })

  it('tolerates a cyclic graph without infinite recursion', () => {
    const d = parseSankey(`sankey-beta
      A,B,1
      B,A,1`)!
    expect(d.nodes).toHaveLength(2)
  })
})

describe('sankeyToElements', () => {
  it('emits one rect + label per node and one line per link', () => {
    const d = parseSankey('sankey-beta\nA,B,5')!
    const els = sankeyToElements(d)
    expect(els.filter((e) => e.type === 'rect')).toHaveLength(2)
    expect(els.filter((e) => e.type === 'line')).toHaveLength(1)
    // Two labels in the text set.
    const labels = els
      .filter((e) => e.type === 'text')
      .map((e) => (e as unknown as { text: string }).text)
    expect(labels).toContain('A (5)')
    expect(labels).toContain('B (5)')
  })

  it('thicker links for larger values', () => {
    const d = parseSankey(`sankey-beta
      A,B,1
      A,C,10`)!
    const els = sankeyToElements(d)
    const lines = els.filter((e) => e.type === 'line') as Array<{
      strokeWidth: number
    }>
    expect(lines).toHaveLength(2)
    // The 10-value link should be thicker than the 1-value link.
    const widths = lines.map((l) => l.strokeWidth)
    expect(Math.max(...widths)).toBeGreaterThan(Math.min(...widths))
  })

  it('places source nodes left of target nodes', () => {
    const d = parseSankey('sankey-beta\nA,B,5')!
    const els = sankeyToElements(d)
    const rects = els.filter((e) => e.type === 'rect') as Array<{
      x: number
    }>
    expect(rects).toHaveLength(2)
    expect(Math.max(...rects.map((r) => r.x))).toBeGreaterThan(
      Math.min(...rects.map((r) => r.x)),
    )
  })

  it('respects the originX / originY offset', () => {
    const d = parseSankey('sankey-beta\nA,B,5')!
    const els = sankeyToElements(d, { originX: 500, originY: 300 })
    const rect = els.find((e) => e.type === 'rect') as { x: number; y: number }
    expect(rect.x).toBeGreaterThanOrEqual(500)
    expect(rect.y).toBeGreaterThanOrEqual(300)
  })

  it('produces deterministic output for a given input', () => {
    const a = sankeyToElements(parseSankey('sankey-beta\nA,B,1\nB,C,1')!)
    const b = sankeyToElements(parseSankey('sankey-beta\nA,B,1\nB,C,1')!)
    expect(JSON.stringify(a)).toBe(JSON.stringify(b))
  })

  it('renders nothing for a diagram with no nodes', () => {
    const d = parseSankey('sankey-beta\n%% no rows')!
    expect(sankeyToElements(d)).toEqual([])
  })
})
