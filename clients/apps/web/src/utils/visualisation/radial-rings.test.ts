import { describe, expect, it } from 'vitest'

import {
  arcCentroid,
  arcPath,
  layoutRingTree,
  treeDepth,
  type RingNode,
} from './radial-rings'

const tree = (): RingNode => ({
  id: 'root',
  children: [
    {
      id: 'a',
      children: [
        { id: 'a1', value: 1 },
        { id: 'a2', value: 1 },
      ],
    },
    {
      id: 'b',
      children: [
        { id: 'b1', value: 2 },
        { id: 'b2', value: 2 },
      ],
    },
  ],
})

describe('treeDepth', () => {
  it('returns 0 for a leaf', () => {
    expect(treeDepth({ id: 'x', value: 1 })).toBe(0)
  })

  it('counts the deepest branch', () => {
    expect(treeDepth(tree())).toBe(2)
  })
})

describe('layoutRingTree', () => {
  it('emits one arc per node in pre-order', () => {
    const arcs = layoutRingTree(tree(), { radius: 100 })
    expect(arcs.map((a) => a.id)).toEqual([
      'root',
      'a',
      'a1',
      'a2',
      'b',
      'b1',
      'b2',
    ])
  })

  it('the root spans a full circle', () => {
    const arcs = layoutRingTree(tree(), { radius: 100 })
    const root = arcs.find((a) => a.id === 'root')!
    expect(root.startAngle).toBeCloseTo(0)
    expect(root.endAngle).toBeCloseTo(Math.PI * 2)
  })

  it("partitions a parent's sweep proportionally to child summed values", () => {
    // a-subtree totals 2, b-subtree totals 4 — so a should occupy a
    // third of the circle and b two-thirds.
    const arcs = layoutRingTree(tree(), { radius: 100 })
    const a = arcs.find((x) => x.id === 'a')!
    const b = arcs.find((x) => x.id === 'b')!
    const aSweep = a.endAngle - a.startAngle
    const bSweep = b.endAngle - b.startAngle
    expect(aSweep / bSweep).toBeCloseTo(1 / 2)
  })

  it("a leaf's value drives its sweep within the parent", () => {
    const arcs = layoutRingTree(
      {
        id: 'root',
        children: [
          { id: 'small', value: 1 },
          { id: 'big', value: 3 },
        ],
      },
      { radius: 100 },
    )
    const small = arcs.find((a) => a.id === 'small')!
    const big = arcs.find((a) => a.id === 'big')!
    expect(big.endAngle - big.startAngle).toBeCloseTo(
      3 * (small.endAngle - small.startAngle),
    )
  })

  it('respects centerRadius — root inner radius is at the centre', () => {
    const arcs = layoutRingTree(tree(), { radius: 200, centerRadius: 0.2 })
    const root = arcs.find((a) => a.id === 'root')!
    expect(root.innerRadius).toBeCloseTo(40) // 0.2 * 200
  })

  it('outer ring of the deepest leaves reaches the configured radius', () => {
    const arcs = layoutRingTree(tree(), { radius: 200 })
    const leaf = arcs.find((a) => a.id === 'a1')!
    expect(leaf.outerRadius).toBeCloseTo(200)
  })

  it('every depth band has positive thickness (no collapsed leaves)', () => {
    const arcs = layoutRingTree(tree(), { radius: 200, centerRadius: 0 })
    for (const a of arcs) {
      expect(a.outerRadius).toBeGreaterThan(a.innerRadius)
    }
  })

  it('radiusScaleExponent=1 produces equal-thickness bands', () => {
    // Tree depth 2 → 3 layers (root, depth-1, depth-2). Even split
    // across [0, 300] = 100/200/300.
    const arcs = layoutRingTree(tree(), {
      radius: 300,
      centerRadius: 0,
      radiusScaleExponent: 1,
    })
    const root = arcs.find((a) => a.id === 'root')!
    const a = arcs.find((x) => x.id === 'a')!
    const a1 = arcs.find((x) => x.id === 'a1')!
    expect(root.outerRadius).toBeCloseTo(100)
    expect(a.outerRadius).toBeCloseTo(200)
    expect(a1.outerRadius).toBeCloseTo(300)
  })

  it('falls back to the default colour for nodes without one', () => {
    const arcs = layoutRingTree(
      { id: 'root', children: [{ id: 'a', value: 1 }] },
      { radius: 100, defaultColor: '#ff00ff' },
    )
    expect(arcs[0].color).toBe('#ff00ff')
    expect(arcs[1].color).toBe('#ff00ff')
  })

  it('uses an explicit per-node colour when provided', () => {
    const arcs = layoutRingTree(
      { id: 'root', color: '#abcdef', children: [{ id: 'a', value: 1 }] },
      { radius: 100 },
    )
    expect(arcs.find((a) => a.id === 'root')!.color).toBe('#abcdef')
  })

  it('emits zero-sweep arcs for nodes whose siblings carry all the value (no NaN)', () => {
    const arcs = layoutRingTree(
      {
        id: 'root',
        children: [
          { id: 'zero', value: 0 },
          { id: 'all', value: 1 },
        ],
      },
      { radius: 100 },
    )
    const zero = arcs.find((a) => a.id === 'zero')!
    expect(zero.startAngle).toBeCloseTo(0)
    expect(zero.endAngle).toBeCloseTo(0)
    expect(Number.isFinite(zero.innerRadius)).toBe(true)
  })

  it('produces deterministic output for a given input', () => {
    const a = layoutRingTree(tree(), { radius: 200 })
    const b = layoutRingTree(tree(), { radius: 200 })
    expect(JSON.stringify(a)).toBe(JSON.stringify(b))
  })
})

describe('arcPath', () => {
  it('emits a wedge (no inner arc) when innerRadius is zero', () => {
    const d = arcPath({
      innerRadius: 0,
      outerRadius: 100,
      startAngle: 0,
      endAngle: Math.PI / 2,
    })
    expect(d.startsWith('M 0 0')).toBe(true)
    expect(d.endsWith('Z')).toBe(true)
  })

  it('emits two arcs and a radial line for a general annular segment', () => {
    const d = arcPath({
      innerRadius: 50,
      outerRadius: 100,
      startAngle: 0,
      endAngle: Math.PI / 2,
    })
    expect(d.split('A').length - 1).toBe(2) // two arc commands
    expect(d).toContain('L ')
    expect(d.endsWith('Z')).toBe(true)
  })

  it('uses largeArc=1 for sweeps greater than π', () => {
    const d = arcPath({
      innerRadius: 0,
      outerRadius: 100,
      startAngle: 0,
      endAngle: Math.PI * 1.5,
    })
    // Two adjacent " 1 " parameters in the arc command — we just
    // assert a 1 appears in the flag block. Positional check is
    // hard to do with regex so this lightweight assertion keeps the
    // test robust against future spacing changes.
    expect(d).toMatch(/A\s+\d+\s+\d+\s+0\s+1\s+1/)
  })

  it('emits a full-circle annulus when sweep is 2π', () => {
    const d = arcPath({
      innerRadius: 50,
      outerRadius: 100,
      startAngle: 0,
      endAngle: Math.PI * 2,
    })
    // Four arc commands total (two for outer full-circle, two for
    // inner full-circle).
    expect(d.split('A').length - 1).toBe(4)
  })
})

describe('arcCentroid', () => {
  it('lies on the bisecting radius at the mid-radius', () => {
    const c = arcCentroid({
      innerRadius: 50,
      outerRadius: 100,
      startAngle: 0,
      endAngle: Math.PI / 2,
    })
    // Bisecting angle = π/4; mid-radius = 75.
    // sin(π/4)*75 ≈ 53.03, -cos(π/4)*75 ≈ -53.03
    expect(c.x).toBeCloseTo(75 * Math.sin(Math.PI / 4))
    expect(c.y).toBeCloseTo(-75 * Math.cos(Math.PI / 4))
  })
})
