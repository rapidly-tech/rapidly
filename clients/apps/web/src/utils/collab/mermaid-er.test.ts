import { describe, expect, it } from 'vitest'

import { erDiagramToElements, parseErDiagram } from './mermaid-er'

describe('parseErDiagram', () => {
  it('returns null when the source is not an ER diagram', () => {
    expect(parseErDiagram('flowchart TD\nA --> B')).toBeNull()
    expect(parseErDiagram('')).toBeNull()
  })

  it('parses a single relationship with auto-created entities', () => {
    const d = parseErDiagram('erDiagram\nCUSTOMER ||--o{ ORDER : places')!
    expect(d.entities.map((e) => e.id).sort()).toEqual(['CUSTOMER', 'ORDER'])
    expect(d.relationships).toHaveLength(1)
    const rel = d.relationships[0]
    expect(rel.from).toBe('CUSTOMER')
    expect(rel.to).toBe('ORDER')
    expect(rel.fromCardinality).toBe('one')
    expect(rel.toCardinality).toBe('zero or more')
    expect(rel.label).toBe('places')
    expect(rel.dashed).toBe(false)
  })

  it('parses an attribute block', () => {
    const d = parseErDiagram(`erDiagram
      CUSTOMER {
        string name
        string email
        int age PK
      }`)!
    const c = d.entities.find((e) => e.id === 'CUSTOMER')!
    expect(c.attributes).toEqual([
      { type: 'string', name: 'name', tags: '' },
      { type: 'string', name: 'email', tags: '' },
      { type: 'int', name: 'age', tags: 'PK' },
    ])
  })

  it('handles the same-line attribute-block form', () => {
    const d = parseErDiagram('erDiagram\nUSER { string id PK }')!
    expect(d.entities[0].attributes).toEqual([
      { type: 'string', name: 'id', tags: 'PK' },
    ])
  })

  it.each([
    ['||--||', 'one', 'one'],
    ['||--o|', 'one', 'zero or one'],
    ['||--|{', 'one', 'one or more'],
    ['||--o{', 'one', 'zero or more'],
    ['|o--||', 'zero or one', 'one'],
    ['}|--||', 'one or more', 'one'],
    ['}o--||', 'zero or more', 'one'],
  ])('parses %s as fromCardinality=%s toCardinality=%s', (op, from, to) => {
    const d = parseErDiagram(`erDiagram\nA ${op} B : x`)!
    const rel = d.relationships[0]
    expect(rel.fromCardinality).toBe(from)
    expect(rel.toCardinality).toBe(to)
  })

  it('detects the dashed (non-identifying) separator ..', () => {
    const d = parseErDiagram('erDiagram\nA ||..o{ B : x')!
    expect(d.relationships[0].dashed).toBe(true)
  })

  it('accepts a relationship without a label', () => {
    const d = parseErDiagram('erDiagram\nA ||--o{ B')!
    expect(d.relationships[0].label).toBe('')
  })

  it('skips comments + tolerates trailing comments', () => {
    const d = parseErDiagram(`erDiagram
      %% comment
      A ||--o{ B : x %% trailing`)!
    expect(d.relationships).toHaveLength(1)
  })

  it('ignores garbled lines without aborting', () => {
    const d = parseErDiagram(`erDiagram
      A ||--o{ B : x
      garbled+++
      C ||--o{ D : y`)!
    expect(d.relationships).toHaveLength(2)
  })
})

describe('erDiagramToElements', () => {
  it('emits rect + header text per empty entity', () => {
    const d = parseErDiagram('erDiagram\nUSER {\n}')!
    const els = erDiagramToElements(d)
    // 1 rect + 1 header text = 2 (no attributes → no divider, no rows).
    expect(els).toHaveLength(2)
    expect(els[0].type).toBe('rect')
  })

  it('emits divider line + per-attribute text for an entity with attributes', () => {
    const d = parseErDiagram(`erDiagram
      USER {
        int id PK
        string name
      }`)!
    const els = erDiagramToElements(d)
    // 1 rect + 1 header + 1 divider + 2 attr texts = 5.
    expect(els).toHaveLength(5)
    expect(els.filter((e) => e.type === 'line')).toHaveLength(1)
    expect(els.filter((e) => e.type === 'text')).toHaveLength(3)
  })

  it('emits one line + label per relationship', () => {
    const d = parseErDiagram('erDiagram\nA ||--o{ B : has')!
    const els = erDiagramToElements(d)
    // 2 entities × (rect + header) = 4, plus 1 relationship line + 1
    // relationship label = 6.
    expect(els).toHaveLength(6)
    const lines = els.filter((e) => e.type === 'line')
    expect(lines).toHaveLength(1)
    const labels = els.filter((e) => e.type === 'text')
    expect(labels).toHaveLength(3) // 2 headers + 1 relationship label
  })

  it('renders dashed (non-identifying) relationships with strokeStyle=dashed', () => {
    const d = parseErDiagram('erDiagram\nA ||..o{ B : x')!
    const lines = erDiagramToElements(d).filter((e) => e.type === 'line')
    expect(lines[0].strokeStyle).toBe('dashed')
  })

  it('respects the originX / originY offset', () => {
    const d = parseErDiagram('erDiagram\nA ||--o{ B')!
    const els = erDiagramToElements(d, { originX: 500, originY: 300 })
    const rect = els.find((e) => e.type === 'rect') as { x: number; y: number }
    expect(rect.x).toBeGreaterThanOrEqual(500)
    expect(rect.y).toBe(300)
  })

  it('lays out entities in a roughly-square grid', () => {
    const d = parseErDiagram('erDiagram\nA ||--o{ B\nC ||--o{ D\nA ||--o{ C')!
    const els = erDiagramToElements(d)
    const rects = els.filter((e) => e.type === 'rect') as Array<{
      x: number
      y: number
    }>
    // 4 entities → 2 columns × 2 rows.
    expect(rects).toHaveLength(4)
    expect(rects[0].y).toBe(rects[1].y)
    expect(rects[2].y).toBeGreaterThan(rects[0].y)
  })
})
