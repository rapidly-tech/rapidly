import { describe, expect, it } from 'vitest'

import { blockDiagramToElements, parseBlockDiagram } from './mermaid-block'

describe('parseBlockDiagram', () => {
  it('returns null when the source is not a block diagram', () => {
    expect(parseBlockDiagram('flowchart TD\nA --> B')).toBeNull()
    expect(parseBlockDiagram('')).toBeNull()
  })

  it('accepts both block-beta and block headers', () => {
    expect(parseBlockDiagram('block-beta\nA')).not.toBeNull()
    expect(parseBlockDiagram('block\nA')).not.toBeNull()
  })

  it('captures the columns directive', () => {
    const d = parseBlockDiagram('block-beta\ncolumns 4\nA B C D')!
    expect(d.columns).toBe(4)
  })

  it('parses three blocks across one row', () => {
    const d = parseBlockDiagram('block-beta\ncolumns 3\nA B C')!
    expect(d.blocks.map((b) => b.id)).toEqual(['A', 'B', 'C'])
    expect(d.blocks.map((b) => b.col)).toEqual([0, 1, 2])
    expect(d.blocks.every((b) => b.row === 0)).toBe(true)
  })

  it('honours per-block span via the :N modifier', () => {
    const d = parseBlockDiagram('block-beta\ncolumns 3\nA:2 B')!
    expect(d.blocks[0].span).toBe(2)
    expect(d.blocks[1].col).toBe(2)
  })

  it('wraps to a new row when the row exceeds the column count', () => {
    const d = parseBlockDiagram('block-beta\ncolumns 2\nA B C')!
    expect(d.blocks[0].row).toBe(0)
    expect(d.blocks[1].row).toBe(0)
    expect(d.blocks[2].row).toBe(1)
  })

  it('recognises shape wrappers', () => {
    const d = parseBlockDiagram(`block-beta
      A["Label"] B(("Cloud")) C("Round")`)!
    expect(d.blocks[0].shape).toBe('rect')
    expect(d.blocks[0].label).toBe('Label')
    expect(d.blocks[1].shape).toBe('circle')
    expect(d.blocks[1].label).toBe('Cloud')
    expect(d.blocks[2].shape).toBe('rounded')
    expect(d.blocks[2].label).toBe('Round')
  })

  it('captures arrow edges with optional labels', () => {
    const d = parseBlockDiagram(`block-beta
      A B
      A --> B
      A -- "go" --> B`)!
    expect(d.edges).toEqual([
      { from: 'A', to: 'B', label: '' },
      { from: 'A', to: 'B', label: 'go' },
    ])
  })

  it('skips comments + tolerates trailing comments', () => {
    const d = parseBlockDiagram(`block-beta
      %% intro
      A B %% trailing`)!
    expect(d.blocks).toHaveLength(2)
  })

  it('ignores garbled lines without aborting', () => {
    const d = parseBlockDiagram(`block-beta
      A B
      garbled+++
      C`)!
    // ``garbled+++`` doesn't match the token regex so it's dropped;
    // A, B, C all get registered as plain blocks.
    expect(d.blocks.map((b) => b.id).sort()).toEqual(['A', 'B', 'C'])
  })
})

describe('blockDiagramToElements', () => {
  it('emits a rect + label per default-shape block', () => {
    const d = parseBlockDiagram('block-beta\ncolumns 3\nA B C')!
    const els = blockDiagramToElements(d)
    expect(els.filter((e) => e.type === 'rect')).toHaveLength(3)
    const labels = els
      .filter((e) => e.type === 'text')
      .map((e) => (e as unknown as { text: string }).text)
    expect(labels.sort()).toEqual(['A', 'B', 'C'])
  })

  it('emits an ellipse for circle-shape blocks', () => {
    const d = parseBlockDiagram('block-beta\nA(("Cloud"))')!
    const els = blockDiagramToElements(d)
    expect(els.filter((e) => e.type === 'ellipse')).toHaveLength(1)
  })

  it('emits one arrow per edge', () => {
    const d = parseBlockDiagram(`block-beta
      A B
      A --> B`)!
    const els = blockDiagramToElements(d)
    expect(els.filter((e) => e.type === 'arrow')).toHaveLength(1)
  })

  it('renders an edge label when set', () => {
    const d = parseBlockDiagram(`block-beta
      A B
      A -- "go" --> B`)!
    const els = blockDiagramToElements(d)
    const labels = els
      .filter((e) => e.type === 'text')
      .map((e) => (e as unknown as { text: string }).text)
    expect(labels).toContain('go')
  })

  it('makes a span-N block N×wider', () => {
    const d = parseBlockDiagram('block-beta\ncolumns 3\nA:2 B')!
    const els = blockDiagramToElements(d)
    const rects = els.filter((e) => e.type === 'rect') as Array<{
      width: number
    }>
    // A.width should be ~2x B.width (140*2 + 12 vs 140).
    expect(rects[0].width).toBeGreaterThan(rects[1].width * 1.5)
  })

  it('respects originX / originY', () => {
    const d = parseBlockDiagram('block-beta\nA')!
    const els = blockDiagramToElements(d, { originX: 500, originY: 300 })
    const rect = els.find((e) => e.type === 'rect') as { x: number; y: number }
    expect(rect.x).toBe(500)
    expect(rect.y).toBe(300)
  })

  it('produces deterministic output for a given input', () => {
    const a = blockDiagramToElements(
      parseBlockDiagram('block-beta\ncolumns 2\nA B\nA --> B')!,
    )
    const b = blockDiagramToElements(
      parseBlockDiagram('block-beta\ncolumns 2\nA B\nA --> B')!,
    )
    expect(JSON.stringify(a)).toBe(JSON.stringify(b))
  })
})
