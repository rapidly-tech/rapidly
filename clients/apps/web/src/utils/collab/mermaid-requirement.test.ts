import { describe, expect, it } from 'vitest'

import {
  parseRequirementDiagram,
  requirementDiagramToElements,
} from './mermaid-requirement'

describe('parseRequirementDiagram', () => {
  it('returns null when the source is not a requirement diagram', () => {
    expect(parseRequirementDiagram('flowchart TD\nA --> B')).toBeNull()
    expect(parseRequirementDiagram('')).toBeNull()
  })

  it('parses a requirement block with attributes', () => {
    const d = parseRequirementDiagram(`requirementDiagram
      requirement test_req {
        id: 1
        text: the test text
        risk: high
      }`)!
    expect(d.blocks).toHaveLength(1)
    const b = d.blocks[0]
    expect(b.id).toBe('test_req')
    expect(b.kind).toBe('requirement')
    expect(b.subkind).toBe('requirement')
    expect(b.attributes).toEqual([
      { key: 'id', value: '1' },
      { key: 'text', value: 'the test text' },
      { key: 'risk', value: 'high' },
    ])
  })

  it('keeps the original keyword as subkind for typed requirements', () => {
    const d = parseRequirementDiagram(`requirementDiagram
      functionalRequirement foo {
        id: 1
      }`)!
    expect(d.blocks[0].subkind).toBe('functionalRequirement')
    expect(d.blocks[0].kind).toBe('requirement')
  })

  it('parses an element block', () => {
    const d = parseRequirementDiagram(`requirementDiagram
      element test_entity {
        type: simulation
      }`)!
    expect(d.blocks[0].kind).toBe('element')
  })

  it('strips surrounding quotes from attribute values', () => {
    const d = parseRequirementDiagram(`requirementDiagram
      requirement R {
        text: "the quoted value"
      }`)!
    expect(d.blocks[0].attributes[0].value).toBe('the quoted value')
  })

  it.each([
    'contains',
    'copies',
    'derives',
    'satisfies',
    'verifies',
    'refines',
    'traces',
  ])('parses the relationship verb "%s"', (verb) => {
    const d = parseRequirementDiagram(`requirementDiagram
      a - ${verb} -> b`)!
    expect(d.relations).toHaveLength(1)
    expect(d.relations[0].verb).toBe(verb)
  })

  it('rejects unknown verbs', () => {
    const d = parseRequirementDiagram(
      'requirementDiagram\na - frobnicate -> b',
    )!
    expect(d.relations).toEqual([])
  })

  it('skips comments + tolerates trailing comments', () => {
    const d = parseRequirementDiagram(`requirementDiagram
      %% comment
      requirement R { id: 1 } %% trailing`)!
    expect(d.blocks).toHaveLength(1)
  })

  it('ignores garbled lines without aborting', () => {
    const d = parseRequirementDiagram(`requirementDiagram
      requirement A { id: 1 }
      garbled+++
      element B { type: x }`)!
    expect(d.blocks).toHaveLength(2)
  })
})

describe('requirementDiagramToElements', () => {
  it('emits rect + stereotype + name per empty block', () => {
    const d = parseRequirementDiagram('requirementDiagram\nrequirement R {\n}')!
    const els = requirementDiagramToElements(d)
    // 1 rect + 1 stereotype + 1 name = 3
    expect(els).toHaveLength(3)
    expect(els[0].type).toBe('rect')
  })

  it('emits divider line + per-attribute text for blocks with attributes', () => {
    const d = parseRequirementDiagram(`requirementDiagram
      requirement R {
        id: 1
        risk: high
      }`)!
    const els = requirementDiagramToElements(d)
    // 1 rect + 1 stereotype + 1 name + 1 divider + 2 attr texts = 6
    expect(els).toHaveLength(6)
    expect(els.filter((e) => e.type === 'line')).toHaveLength(1)
    expect(els.filter((e) => e.type === 'text')).toHaveLength(4) // 1 stereo + 1 name + 2 attrs
  })

  it('emits one arrow + verb label per relationship', () => {
    const d = parseRequirementDiagram(`requirementDiagram
      requirement A { id: 1 }
      element B { type: x }
      A - satisfies -> B`)!
    const els = requirementDiagramToElements(d)
    expect(els.filter((e) => e.type === 'arrow')).toHaveLength(1)
    const verbLabels = els
      .filter((e) => e.type === 'text')
      .map((e) => (e as unknown as { text: string }).text)
    expect(verbLabels).toContain('«satisfies»')
  })

  it('respects the originX / originY offset', () => {
    const d = parseRequirementDiagram('requirementDiagram\nrequirement R {\n}')!
    const els = requirementDiagramToElements(d, {
      originX: 500,
      originY: 300,
    })
    const rect = els.find((e) => e.type === 'rect') as { x: number; y: number }
    expect(rect.x).toBe(500)
    expect(rect.y).toBe(300)
  })

  it('lays out blocks in a roughly-square grid', () => {
    const d = parseRequirementDiagram(`requirementDiagram
      requirement A {}
      requirement B {}
      requirement C {}
      requirement D {}`)!
    const els = requirementDiagramToElements(d)
    const rects = els.filter((e) => e.type === 'rect') as Array<{
      x: number
      y: number
    }>
    expect(rects).toHaveLength(4)
    // 4 → 2 columns by default, so rect 0 and rect 1 share a y, and
    // rect 2's y should be lower.
    expect(rects[0].y).toBe(rects[1].y)
    expect(rects[2].y).toBeGreaterThan(rects[0].y)
  })

  it('produces deterministic output for a given input', () => {
    const a = requirementDiagramToElements(
      parseRequirementDiagram(
        `requirementDiagram\nrequirement A { id: 1 }\nelement B { type: x }\nA - satisfies -> B`,
      )!,
    )
    const b = requirementDiagramToElements(
      parseRequirementDiagram(
        `requirementDiagram\nrequirement A { id: 1 }\nelement B { type: x }\nA - satisfies -> B`,
      )!,
    )
    expect(JSON.stringify(a)).toBe(JSON.stringify(b))
  })
})
