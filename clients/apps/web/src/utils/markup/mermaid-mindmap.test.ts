import { describe, expect, it } from 'vitest'

import { mindmapToElements, parseMindmap } from './mermaid-mindmap'

describe('parseMindmap', () => {
  it('returns null when the source is not a mindmap', () => {
    expect(parseMindmap('flowchart TD\nA --> B')).toBeNull()
    expect(parseMindmap('')).toBeNull()
  })

  it('returns an empty diagram when the body has no nodes', () => {
    const d = parseMindmap('mindmap\n  %% only a comment')!
    expect(d.root).toBeNull()
    expect(d.nodeCount).toBe(0)
  })

  it('parses a single root node', () => {
    const d = parseMindmap('mindmap\n  root((Hello))')!
    expect(d.root).not.toBeNull()
    expect(d.root!.label).toBe('Hello')
    expect(d.root!.shape).toBe('circle')
    expect(d.root!.children).toEqual([])
    expect(d.nodeCount).toBe(1)
  })

  it('builds a one-level child tree from indentation', () => {
    const d = parseMindmap(`mindmap
  root((R))
    Branch A
    Branch B`)!
    expect(d.root!.children).toHaveLength(2)
    expect(d.root!.children.map((c) => c.label)).toEqual([
      'Branch A',
      'Branch B',
    ])
  })

  it('handles deeper nesting', () => {
    const d = parseMindmap(`mindmap
  root
    A
      A1
      A2
    B`)!
    const a = d.root!.children[0]
    expect(a.label).toBe('A')
    expect(a.children.map((c) => c.label)).toEqual(['A1', 'A2'])
    const b = d.root!.children[1]
    expect(b.label).toBe('B')
    expect(b.children).toEqual([])
  })

  it('recognises shape tokens (((cloud)) [rect] (rounded))', () => {
    const d = parseMindmap(`mindmap
  ((Cloud))
    [Rect]
    (Rounded)
    Default`)!
    expect(d.root!.shape).toBe('circle')
    const [rect, rounded, def] = d.root!.children
    expect(rect.shape).toBe('rect')
    expect(rounded.shape).toBe('rounded')
    expect(def.shape).toBe('default')
  })

  it('skips comments + tolerates trailing comments', () => {
    const d = parseMindmap(`mindmap
  %% header comment
  root
    A %% trailing`)!
    expect(d.root!.children).toHaveLength(1)
  })

  it('promotes to a synthetic root when multiple top-level entries appear', () => {
    const d = parseMindmap(`mindmap
  Alpha
  Beta`)!
    // Two depth-0 entries → synthetic root with both as children.
    expect(d.root!.label).toBe('Mindmap')
    expect(d.root!.children.map((c) => c.label).sort()).toEqual([
      'Alpha',
      'Beta',
    ])
  })

  it('counts every node regardless of depth', () => {
    const d = parseMindmap(`mindmap
  root
    A
      A1
    B`)!
    expect(d.nodeCount).toBe(4)
  })
})

describe('mindmapToElements', () => {
  it('emits no elements for an empty diagram', () => {
    const d = parseMindmap('mindmap\n  %% nothing')!
    expect(mindmapToElements(d)).toEqual([])
  })

  it('places the root at the origin', () => {
    const d = parseMindmap('mindmap\n  root((R))')!
    const els = mindmapToElements(d, { originX: 100, originY: 200 })
    const ellipse = els.find((e) => e.type === 'ellipse') as {
      x: number
      y: number
      width: number
      height: number
    }
    // Root is centred on (originX, originY) — its top-left is the
    // centre minus half its dimensions.
    expect(ellipse.x + ellipse.width / 2).toBe(100)
    expect(ellipse.y + ellipse.height / 2).toBe(200)
  })

  it('renders a connector line per parent→child edge', () => {
    const d = parseMindmap(`mindmap
  root
    A
    B
    C`)!
    const els = mindmapToElements(d)
    const lines = els.filter((e) => e.type === 'line')
    expect(lines).toHaveLength(3)
  })

  it('emits one shape + one label per node', () => {
    const d = parseMindmap(`mindmap
  root
    A
    B`)!
    const els = mindmapToElements(d)
    // 1 root (ellipse) + 2 children (rect or ellipse depending on
    // shape — default is rect) + 3 labels + 2 connectors = 8.
    const texts = els.filter((e) => e.type === 'text')
    expect(texts).toHaveLength(3)
    const shapes = els.filter((e) => e.type === 'rect' || e.type === 'ellipse')
    expect(shapes).toHaveLength(3)
  })

  it('produces deterministic output for a given input', () => {
    const a = mindmapToElements(parseMindmap('mindmap\n  root\n    A\n    B')!)
    const b = mindmapToElements(parseMindmap('mindmap\n  root\n    A\n    B')!)
    expect(JSON.stringify(a)).toBe(JSON.stringify(b))
  })

  it('places first-level children at non-zero radius from the root', () => {
    const d = parseMindmap('mindmap\n  root\n    A')!
    const els = mindmapToElements(d, { originX: 0, originY: 0 })
    // The single child should land somewhere on the depth-1 ring,
    // i.e. at distance > 0 from the origin.
    const shapes = els.filter(
      (e) => e.type === 'rect' || e.type === 'ellipse',
    ) as Array<{ x: number; y: number; width: number; height: number }>
    expect(shapes).toHaveLength(2)
    const child = shapes[1]
    const cx = child.x + child.width / 2
    const cy = child.y + child.height / 2
    expect(Math.hypot(cx, cy)).toBeGreaterThan(0)
  })
})
