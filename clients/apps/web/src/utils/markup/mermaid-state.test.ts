import { describe, expect, it } from 'vitest'

import {
  computeLayers,
  parseStateDiagram,
  stateDiagramToElements,
} from './mermaid-state'

describe('parseStateDiagram', () => {
  it('returns null when the source is not a state diagram', () => {
    expect(parseStateDiagram('flowchart TD\nA --> B')).toBeNull()
    expect(parseStateDiagram('')).toBeNull()
  })

  it('accepts both stateDiagram and stateDiagram-v2 headers', () => {
    expect(parseStateDiagram('stateDiagram\nA --> B')).not.toBeNull()
    expect(parseStateDiagram('stateDiagram-v2\nA --> B')).not.toBeNull()
  })

  it('parses a transition + auto-creates referenced states', () => {
    const d = parseStateDiagram('stateDiagram\nA --> B')!
    expect(Array.from(d.nodes.keys()).sort()).toEqual(['A', 'B'])
    expect(d.transitions).toEqual([{ from: 'A', to: 'B', label: '' }])
  })

  it('captures the optional transition label', () => {
    const d = parseStateDiagram('stateDiagram\nA --> B : start')!
    expect(d.transitions[0].label).toBe('start')
  })

  it('treats [*] as the terminal pseudo-state', () => {
    const d = parseStateDiagram(`stateDiagram
      [*] --> A
      A --> [*]`)!
    expect(d.nodes.get('[*]')?.terminal).toBe(true)
    expect(d.nodes.get('[*]')?.label).toBe('')
    expect(d.transitions).toHaveLength(2)
    expect(d.transitions[0].from).toBe('[*]')
    expect(d.transitions[1].to).toBe('[*]')
  })

  it('honours `state X as Friendly` aliases', () => {
    const d = parseStateDiagram(`stateDiagram
      state A as Active
      [*] --> A`)!
    expect(d.nodes.get('A')?.label).toBe('Active')
  })

  it('honours the quoted-label alt form `state "Long Name" as A`', () => {
    const d = parseStateDiagram(`stateDiagram
      state "Long Name" as A
      [*] --> A`)!
    expect(d.nodes.get('A')?.label).toBe('Long Name')
  })

  it('skips comments + tolerates trailing comments', () => {
    const d = parseStateDiagram(`stateDiagram
      %% header comment
      A --> B %% trailing`)!
    expect(d.transitions).toHaveLength(1)
  })

  it('flattens nested state blocks (parent containment dropped)', () => {
    const d = parseStateDiagram(`stateDiagram
      state Parent {
        [*] --> Sub
        Sub --> [*]
      }`)!
    // ``state Parent`` declares Parent; the body's transitions land
    // as if they were top-level. ``[*]`` and ``Sub`` get auto-created.
    expect(d.nodes.has('Parent')).toBe(true)
    expect(d.nodes.has('Sub')).toBe(true)
    expect(d.nodes.has('[*]')).toBe(true)
  })

  it('ignores garbled lines without aborting', () => {
    const d = parseStateDiagram(`stateDiagram
      A --> B
      garbled+++
      B --> C`)!
    expect(d.transitions).toHaveLength(2)
  })
})

describe('computeLayers', () => {
  it('places a chain on monotonically-increasing layers', () => {
    const d = parseStateDiagram(`stateDiagram
      A --> B
      B --> C`)!
    const layers = computeLayers(d)
    expect(layers.get('A')).toBe(0)
    expect(layers.get('B')).toBe(1)
    expect(layers.get('C')).toBe(2)
  })

  it('tolerates a back-edge cycle without infinite recursion', () => {
    const d = parseStateDiagram(`stateDiagram
      A --> B
      B --> A`)!
    expect(() => computeLayers(d)).not.toThrow()
  })
})

describe('stateDiagramToElements', () => {
  it('renders a normal state as a rounded rect + centred label', () => {
    const d = parseStateDiagram('stateDiagram\nA --> B')!
    const els = stateDiagramToElements(d)
    const rects = els.filter((e) => e.type === 'rect')
    expect(rects).toHaveLength(2)
    const texts = els.filter((e) => e.type === 'text')
    expect(texts).toHaveLength(2) // one label per state
  })

  it('renders [*] as a small filled ellipse', () => {
    const d = parseStateDiagram('stateDiagram\n[*] --> A')!
    const els = stateDiagramToElements(d)
    const ellipses = els.filter((e) => e.type === 'ellipse')
    expect(ellipses).toHaveLength(1)
    // No accompanying text element for the terminal.
    const labelTexts = els.filter(
      (e) =>
        e.type === 'text' && (e as unknown as { text: string }).text === '',
    )
    expect(labelTexts).toHaveLength(0)
  })

  it('emits one arrow per transition + a label text when set', () => {
    const d = parseStateDiagram(`stateDiagram
      A --> B : start
      B --> C`)!
    const els = stateDiagramToElements(d)
    const arrows = els.filter((e) => e.type === 'arrow')
    expect(arrows).toHaveLength(2)
    // Labels: 1 transition label + 3 state labels = 4 text elements.
    const texts = els.filter((e) => e.type === 'text')
    expect(texts).toHaveLength(4)
  })

  it('respects the originX / originY offset', () => {
    const d = parseStateDiagram('stateDiagram\n[*] --> A')!
    const els = stateDiagramToElements(d, { originX: 500, originY: 300 })
    const allXs = els.filter((e) => 'x' in e).map((e) => (e as { x: number }).x)
    // Every element should be at or beyond the origin (some are
    // centred so could equal it; none should be far below).
    expect(Math.min(...allXs)).toBeGreaterThanOrEqual(490)
  })

  it('produces deterministic layout for a given input', () => {
    const a = stateDiagramToElements(
      parseStateDiagram('stateDiagram\n[*] --> A\nA --> [*]')!,
    )
    const b = stateDiagramToElements(
      parseStateDiagram('stateDiagram\n[*] --> A\nA --> [*]')!,
    )
    expect(JSON.stringify(a)).toBe(JSON.stringify(b))
  })
})
