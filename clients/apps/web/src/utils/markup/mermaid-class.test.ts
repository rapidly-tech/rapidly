import { describe, expect, it } from 'vitest'

import { classDiagramToElements, parseClassDiagram } from './mermaid-class'

describe('parseClassDiagram', () => {
  it('returns null when the source is not a class diagram', () => {
    expect(parseClassDiagram('flowchart TD\nA --> B')).toBeNull()
    expect(parseClassDiagram('')).toBeNull()
  })

  it('parses an empty-body class declaration', () => {
    const d = parseClassDiagram('classDiagram\nclass Animal')!
    expect(d.classes).toHaveLength(1)
    expect(d.classes[0].id).toBe('Animal')
    expect(d.classes[0].members).toEqual([])
  })

  it('captures multi-line member bodies', () => {
    const d = parseClassDiagram(`classDiagram
      class Animal {
        +String name
        +int age
        +eat() void
      }`)!
    const a = d.classes[0]
    expect(a.members).toEqual(['String name', 'int age', 'eat() void'])
  })

  it('strips access modifiers (+ - # ~) from member lines', () => {
    const d = parseClassDiagram(`classDiagram
      class A {
        +pub
        -priv
        #prot
        ~pkg
      }`)!
    expect(d.classes[0].members).toEqual(['pub', 'priv', 'prot', 'pkg'])
  })

  it('handles the same-line brace form', () => {
    const d = parseClassDiagram('classDiagram\nclass Tiny { +x }')!
    expect(d.classes[0].members).toEqual(['x'])
  })

  it.each([
    ['<|--', 'inheritance', false],
    ['--|>', 'inheritance', false],
    ['<|..', 'realization', true],
    ['..|>', 'realization', true],
    ['*--', 'composition', false],
    ['--*', 'composition', false],
    ['o--', 'aggregation', false],
    ['--o', 'aggregation', false],
    ['<--', 'association-directed', false],
    ['-->', 'association-directed', false],
    ['<..', 'dependency', true],
    ['..>', 'dependency', true],
    ['..', 'association', true],
    ['--', 'association', false],
  ])('parses %s as kind=%s dashed=%s', (op, kind, dashed) => {
    const d = parseClassDiagram(`classDiagram\nA ${op} B`)!
    expect(d.relations).toHaveLength(1)
    expect(d.relations[0].kind).toBe(kind)
    expect(d.relations[0].dashed).toBe(dashed)
  })

  it('auto-creates classes referenced only by relations', () => {
    const d = parseClassDiagram('classDiagram\nDog <|-- Puppy')!
    expect(d.classes.map((c) => c.id).sort()).toEqual(['Dog', 'Puppy'])
  })

  it('skips comments + tolerates trailing comments', () => {
    const d = parseClassDiagram(`classDiagram
      %% comment
      class A
      A --> B %% trailing`)!
    expect(d.classes).toHaveLength(2)
    expect(d.relations).toHaveLength(1)
  })

  it('drops cardinality / label suffixes on relationships', () => {
    // Mermaid lets you write ``A --> B : has`` — we ignore the label
    // suffix in v1 rather than mis-parsing it as a third class.
    const d = parseClassDiagram('classDiagram\nA --> B : has')!
    expect(d.relations).toHaveLength(1)
    expect(d.relations[0].from).toBe('A')
    expect(d.relations[0].to).toBe('B')
  })

  it('ignores unrecognised syntax without aborting', () => {
    const d = parseClassDiagram(`classDiagram
      class A
      <<interface>> A
      A --> B
      garbled+++`)!
    expect(d.classes.map((c) => c.id).sort()).toEqual(['A', 'B'])
    expect(d.relations).toHaveLength(1)
  })
})

describe('classDiagramToElements', () => {
  it('emits one rect + header text per empty class', () => {
    const d = parseClassDiagram('classDiagram\nclass A')!
    const els = classDiagramToElements(d)
    // 1 rect + 1 header text = 2 (no members → no divider, no member rows).
    expect(els).toHaveLength(2)
    expect(els[0].type).toBe('rect')
    expect(els[1].type).toBe('text')
  })

  it('emits a divider line + per-member text for a class with members', () => {
    const d = parseClassDiagram(`classDiagram
      class A {
        +x
        +y
      }`)!
    const els = classDiagramToElements(d)
    // 1 rect + 1 header + 1 divider line + 2 member rows = 5.
    expect(els).toHaveLength(5)
    const lines = els.filter((e) => e.type === 'line')
    expect(lines).toHaveLength(1)
    const texts = els.filter((e) => e.type === 'text')
    expect(texts).toHaveLength(3) // header + 2 members
  })

  it('emits one arrow per relationship', () => {
    const d = parseClassDiagram('classDiagram\nA <|-- B\nA --> C')!
    const els = classDiagramToElements(d)
    const arrows = els.filter((e) => e.type === 'arrow')
    expect(arrows).toHaveLength(2)
  })

  it('uses a dashed strokeStyle for dependency / realization', () => {
    const d = parseClassDiagram('classDiagram\nA ..> B')!
    const arrows = classDiagramToElements(d).filter((e) => e.type === 'arrow')
    expect(arrows[0].strokeStyle).toBe('dashed')
  })

  it('omits the arrow head for plain association (--)', () => {
    const d = parseClassDiagram('classDiagram\nA -- B')!
    const arrow = classDiagramToElements(d).find((e) => e.type === 'arrow') as
      | { endArrowhead: unknown }
      | undefined
    expect(arrow?.endArrowhead).toBeNull()
  })

  it('respects the originX / originY offset', () => {
    const d = parseClassDiagram('classDiagram\nclass A')!
    const els = classDiagramToElements(d, { originX: 500, originY: 300 })
    const rect = els.find((e) => e.type === 'rect') as { x: number; y: number }
    expect(rect.x).toBe(500)
    expect(rect.y).toBe(300)
  })

  it('lays out classes in a roughly-square grid', () => {
    // 4 classes → 2 columns by default (ceil(sqrt(4)) = 2).
    const d = parseClassDiagram(
      'classDiagram\nclass A\nclass B\nclass C\nclass D',
    )!
    const els = classDiagramToElements(d)
    const rects = els.filter((e) => e.type === 'rect') as Array<{
      x: number
      y: number
    }>
    // Row 0: A and B at the same y; row 1: C and D at the same lower y.
    expect(rects[0].y).toBe(rects[1].y)
    expect(rects[2].y).toBe(rects[3].y)
    expect(rects[2].y).toBeGreaterThan(rects[0].y)
  })
})
