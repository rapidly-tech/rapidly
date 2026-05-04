import { describe, expect, it } from 'vitest'

import {
  detectMermaidChartType,
  mermaidToElements,
  parseMermaid,
} from './mermaid'

describe('parseMermaid', () => {
  it('returns null when the source is not a recognisable flowchart', () => {
    expect(parseMermaid('')).toBeNull()
    expect(parseMermaid('hello world')).toBeNull()
    expect(parseMermaid('sequenceDiagram\n  A->>B: hi')).toBeNull()
  })

  it('accepts `flowchart TD` and defaults shape to rect', () => {
    const diagram = parseMermaid(`flowchart TD
      A[Start]
      B
      A --> B`)!
    expect(diagram).not.toBeNull()
    expect(diagram.direction).toBe('TD')
    expect(diagram.nodes.get('A')).toEqual({
      id: 'A',
      label: 'Start',
      shape: 'rect',
    })
    expect(diagram.nodes.get('B')).toEqual({
      id: 'B',
      label: 'B',
      shape: 'rect',
    })
    expect(diagram.edges).toEqual([{ from: 'A', to: 'B', arrow: true }])
  })

  it('accepts `graph LR` as an alias for `flowchart LR`', () => {
    const diagram = parseMermaid('graph LR\nA --> B')!
    expect(diagram.direction).toBe('LR')
  })

  it('parses rounded + diamond shapes', () => {
    const diagram = parseMermaid(`flowchart TD
      A(Rounded)
      B{Decision}`)!
    expect(diagram.nodes.get('A')!.shape).toBe('rounded')
    expect(diagram.nodes.get('B')!.shape).toBe('diamond')
  })

  it('strips quoted labels', () => {
    const diagram = parseMermaid('flowchart TD\nA["Label with spaces"]')!
    expect(diagram.nodes.get('A')!.label).toBe('Label with spaces')
  })

  it('distinguishes arrow vs line edges', () => {
    const diagram = parseMermaid(`flowchart TD
      A --> B
      C --- D`)!
    expect(diagram.edges[0].arrow).toBe(true)
    expect(diagram.edges[1].arrow).toBe(false)
  })

  it('expands chained edges on a single line', () => {
    const diagram = parseMermaid('flowchart TD\nA --> B --> C')!
    expect(diagram.edges).toEqual([
      { from: 'A', to: 'B', arrow: true },
      { from: 'B', to: 'C', arrow: true },
    ])
  })

  it('skips comment lines', () => {
    const diagram = parseMermaid(`flowchart TD
      %% this is a comment
      A --> B
      %% inline %%comment trail on an edge
      B --> C %% trailing comment`)!
    expect(diagram.edges).toHaveLength(2)
    expect(diagram.nodes.size).toBe(3)
  })

  it('tolerates garbled lines without aborting the parse', () => {
    const diagram = parseMermaid(`flowchart TD
      !!!nonsense!!!
      A --> B`)!
    expect(diagram.edges).toHaveLength(1)
  })
})

describe('mermaidToElements', () => {
  it('emits a rect + arrow for a two-node flow', () => {
    const diagram = parseMermaid('flowchart TD\nA --> B')!
    const elements = mermaidToElements(diagram)
    // Two nodes + one arrow.
    expect(elements).toHaveLength(3)
    expect(elements[0].type).toBe('rect')
    expect(elements[1].type).toBe('rect')
    expect(elements[2].type).toBe('arrow')
  })

  it('emits diamonds and rounded rects with roundness', () => {
    const diagram = parseMermaid('flowchart TD\nA{Q}\nB(Ro)\nA --> B')!
    const elements = mermaidToElements(diagram)
    const shapes = elements
      .filter((e) => e.type === 'diamond' || e.type === 'rect')
      .map((e) => ({
        type: e.type,
        roundness: (e as unknown as { roundness?: number }).roundness,
      }))
    expect(shapes).toContainEqual({ type: 'diamond', roundness: 0 })
    expect(shapes).toContainEqual({ type: 'rect', roundness: 16 })
  })

  it('uses vertical layers for TD and horizontal for LR', () => {
    const td = mermaidToElements(parseMermaid('flowchart TD\nA --> B')!)
    const lr = mermaidToElements(parseMermaid('flowchart LR\nA --> B')!)
    // TD: node B below node A (larger y).
    const tdA = td[0] as { x: number; y: number }
    const tdB = td[1] as { x: number; y: number }
    expect(tdB.y).toBeGreaterThan(tdA.y)
    // LR: node B right of node A (larger x).
    const lrA = lr[0] as { x: number; y: number }
    const lrB = lr[1] as { x: number; y: number }
    expect(lrB.x).toBeGreaterThan(lrA.x)
  })

  it('respects the origin option', () => {
    const elements = mermaidToElements(parseMermaid('flowchart TD\nA --> B')!, {
      originX: 100,
      originY: 200,
    })
    const first = elements[0] as { x: number; y: number }
    expect(first.x).toBeGreaterThanOrEqual(100)
    expect(first.y).toBeGreaterThanOrEqual(200)
  })

  it('produces a stable ordering for a given input (alpha-sorted within layer)', () => {
    const a = mermaidToElements(
      parseMermaid('flowchart TD\nA --> C\nA --> B\nA --> D')!,
    )
    const b = mermaidToElements(
      parseMermaid('flowchart TD\nA --> C\nA --> B\nA --> D')!,
    )
    // Positions and types must line up identically across runs.
    expect(JSON.stringify(a)).toBe(JSON.stringify(b))
  })

  it('layout assigns independent trees to their own layer 0', () => {
    const diagram = parseMermaid(`flowchart TD
      A --> B
      C --> D`)!
    const elements = mermaidToElements(diagram)
    // Four rects all exist.
    const rects = elements.filter(
      (e) => e.type === 'rect',
    ) as unknown as Array<{
      x: number
      y: number
    }>
    expect(rects).toHaveLength(4)
  })

  it('renders a flowchart with a cycle without throwing', () => {
    const diagram = parseMermaid(`flowchart TD
      A --> B
      B --> A`)!
    expect(() => mermaidToElements(diagram)).not.toThrow()
  })
})

describe('detectMermaidChartType', () => {
  it('returns null for non-Mermaid input', () => {
    expect(detectMermaidChartType('')).toBeNull()
    expect(detectMermaidChartType('hello world')).toBeNull()
    expect(detectMermaidChartType('def foo():\n  pass')).toBeNull()
  })

  it('detects flowchart and graph (the two we render)', () => {
    expect(detectMermaidChartType('flowchart TD\n A --> B')).toBe('flowchart')
    expect(detectMermaidChartType('graph LR\n A --> B')).toBe('graph')
    // Case-insensitive on the keyword.
    expect(detectMermaidChartType('FLOWCHART TD\n A --> B')).toBe('flowchart')
  })

  it.each([
    ['sequenceDiagram', 'sequenceDiagram\n  A->>B: hi'],
    ['classDiagram', 'classDiagram\n  class Foo'],
    ['stateDiagram', 'stateDiagram\n  [*] --> Idle'],
    ['stateDiagram', 'stateDiagram-v2\n  [*] --> Idle'], // versioned variant
    ['erDiagram', 'erDiagram\n  CUSTOMER ||--o{ ORDER : places'],
    ['journey', 'journey\n  title My day'],
    ['gantt', 'gantt\n  title Schedule'],
    ['pie', 'pie\n  title Slices'],
    ['requirementDiagram', 'requirementDiagram\n  requirement test_req'],
    ['gitGraph', 'gitGraph\n  commit'],
    ['C4Context', 'C4Context\n  title System Context'],
    ['mindmap', 'mindmap\n  root((Centre))'],
    ['timeline', 'timeline\n  title Roadmap'],
    ['zenuml', 'zenuml\n  A.do_thing()'],
    ['sankey', 'sankey\n  Source,Sink,5'],
    ['xychart', 'xychart-beta\n  title XY'],
    ['block', 'block\n  columns 3'],
    ['quadrantChart', 'quadrantChart\n  title Reach vs Effort'],
    ['packet', 'packet\n  0-15: src'],
  ])('detects %s', (expected, source) => {
    expect(detectMermaidChartType(source)).toBe(expected)
  })

  it('skips leading blank and comment lines', () => {
    const src = '\n\n%% leading comment\n\nflowchart TD\n  A --> B'
    expect(detectMermaidChartType(src)).toBe('flowchart')
  })

  it('returns null when the first non-comment line isn\'t a known kind', () => {
    expect(
      detectMermaidChartType('%% comment\nsomeUnknownChart\n  body'),
    ).toBeNull()
  })
})
