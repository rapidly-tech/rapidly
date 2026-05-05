import { describe, expect, it } from 'vitest'

import { c4ToElements, parseC4 } from './mermaid-c4'

describe('parseC4', () => {
  it('returns null when the source is not a C4 diagram', () => {
    expect(parseC4('flowchart TD\nA --> B')).toBeNull()
    expect(parseC4('')).toBeNull()
  })

  it('accepts every C4 header variant', () => {
    expect(parseC4('C4Context')).not.toBeNull()
    expect(parseC4('C4Container')).not.toBeNull()
    expect(parseC4('C4Component')).not.toBeNull()
    expect(parseC4('C4Dynamic')).not.toBeNull()
    expect(parseC4('C4Deployment')).not.toBeNull()
  })

  it('parses title + person + system + rel', () => {
    const c = parseC4(`C4Context
      title Banking
      Person(c, "Customer", "uses the bank")
      System(s, "API", "core banking")
      Rel(c, s, "uses", "HTTPS")`)!
    expect(c.title).toBe('Banking')
    expect(c.nodes).toHaveLength(2)
    expect(c.nodes[0]).toEqual({
      id: 'c',
      kind: 'Person',
      label: 'Customer',
      description: 'uses the bank',
      boundary: null,
    })
    expect(c.rels).toEqual([
      {
        from: 'c',
        to: 's',
        label: 'uses',
        technology: 'HTTPS',
        bidirectional: false,
      },
    ])
  })

  it('captures _Ext variants as external nodes', () => {
    const c = parseC4(`C4Context
      System_Ext(e, "Mainframe")
      Person_Ext(p, "Auditor")`)!
    const kinds = c.nodes.map((n) => n.kind)
    expect(kinds).toContain('SystemExt')
    expect(kinds).toContain('PersonExt')
  })

  it('groups nodes inside System_Boundary', () => {
    const c = parseC4(`C4Context
      System_Boundary(b, "Banking") {
        System(s1, "API")
        System(s2, "DB")
      }
      System(s3, "Outside")`)!
    expect(c.boundaries).toHaveLength(1)
    expect(c.nodes.find((n) => n.id === 's1')!.boundary).toBe('b')
    expect(c.nodes.find((n) => n.id === 's2')!.boundary).toBe('b')
    expect(c.nodes.find((n) => n.id === 's3')!.boundary).toBeNull()
  })

  it('marks BiRel as bidirectional', () => {
    const c = parseC4(`C4Context
      System(a, "A")
      System(b, "B")
      BiRel(a, b, "talks to")`)!
    expect(c.rels[0].bidirectional).toBe(true)
  })

  it('respects quoted commas inside argument labels', () => {
    const c = parseC4(`C4Context
      Person(c, "Customer, retail", "shops here")`)!
    expect(c.nodes[0].label).toBe('Customer, retail')
    expect(c.nodes[0].description).toBe('shops here')
  })

  it('skips comments + tolerates trailing comments', () => {
    const c = parseC4(`C4Context
      %% intro
      System(s, "X") %% trailing`)!
    expect(c.nodes).toHaveLength(1)
  })

  it('ignores garbled lines without aborting', () => {
    const c = parseC4(`C4Context
      System(a, "A")
      garbled+++
      System(b, "B")`)!
    expect(c.nodes).toHaveLength(2)
  })
})

describe('c4ToElements', () => {
  it('emits one rect + label set per node and one arrow per rel', () => {
    const c = parseC4(`C4Context
      Person(p, "Customer")
      System(s, "API")
      Rel(p, s, "uses")`)!
    const els = c4ToElements(c)
    expect(els.filter((e) => e.type === 'rect')).toHaveLength(2)
    expect(els.filter((e) => e.type === 'arrow')).toHaveLength(1)
  })

  it('renders the title text when set', () => {
    const c = parseC4('C4Context\ntitle Hello\nSystem(s, "X")')!
    const els = c4ToElements(c)
    const titles = els.filter(
      (e) =>
        e.type === 'text' &&
        (e as unknown as { text: string }).text === 'Hello',
    )
    expect(titles).toHaveLength(1)
  })

  it('renders an external system with a dashed stroke', () => {
    const c = parseC4('C4Context\nSystem_Ext(e, "Mainframe")')!
    const els = c4ToElements(c)
    const rect = els.find((e) => e.type === 'rect') as unknown as {
      strokeStyle: string
    }
    expect(rect.strokeStyle).toBe('dashed')
  })

  it('renders a non-external system with a solid stroke', () => {
    const c = parseC4('C4Context\nSystem(s, "API")')!
    const els = c4ToElements(c)
    const rect = els.find((e) => e.type === 'rect') as unknown as {
      strokeStyle: string
    }
    expect(rect.strokeStyle).toBe('solid')
  })

  it('renders the boundary as a separate dashed rect with its label', () => {
    const c = parseC4(`C4Context
      System_Boundary(b, "Banking") {
        System(s, "API")
      }`)!
    const els = c4ToElements(c)
    const rects = els.filter((e) => e.type === 'rect')
    // 1 boundary + 1 system = 2.
    expect(rects).toHaveLength(2)
    const labels = els
      .filter((e) => e.type === 'text')
      .map((e) => (e as unknown as { text: string }).text)
    expect(labels).toContain('Banking')
  })

  it('emits a BiRel as an arrow with both arrowheads', () => {
    const c = parseC4(`C4Context
      System(a, "A")
      System(b, "B")
      BiRel(a, b, "")`)!
    const els = c4ToElements(c)
    const arrow = els.find((e) => e.type === 'arrow') as unknown as {
      startArrowhead: string | null
      endArrowhead: string | null
    }
    expect(arrow.startArrowhead).toBe('arrow')
    expect(arrow.endArrowhead).toBe('arrow')
  })

  it('skips rels referencing unknown nodes instead of crashing', () => {
    const c = parseC4(`C4Context
      System(a, "A")
      Rel(a, ghost, "uses")`)!
    const els = c4ToElements(c)
    expect(els.filter((e) => e.type === 'arrow')).toHaveLength(0)
  })

  it('respects originX / originY', () => {
    const c = parseC4('C4Context\nSystem(s, "X")')!
    const els = c4ToElements(c, { originX: 500, originY: 300 })
    const rect = els.find((e) => e.type === 'rect') as { x: number; y: number }
    expect(rect.x).toBeGreaterThanOrEqual(500)
    expect(rect.y).toBeGreaterThanOrEqual(300)
  })

  it('produces deterministic output for a given input', () => {
    const a = c4ToElements(
      parseC4('C4Context\nSystem(a, "A")\nSystem(b, "B")\nRel(a, b, "")')!,
    )
    const b = c4ToElements(
      parseC4('C4Context\nSystem(a, "A")\nSystem(b, "B")\nRel(a, b, "")')!,
    )
    expect(JSON.stringify(a)).toBe(JSON.stringify(b))
  })

  it('renders nothing meaningful for an empty diagram', () => {
    const c = parseC4('C4Context\n%% no content')!
    expect(c4ToElements(c)).toEqual([])
  })
})
