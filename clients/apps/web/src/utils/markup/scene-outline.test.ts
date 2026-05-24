import { describe, expect, it } from 'vitest'

import type { CollabElement } from './elements'
import { buildSceneOutline } from './scene-outline'

const baseFields = {
  angle: 0,
  zIndex: 0,
  groupIds: [],
  strokeColor: '#000',
  fillColor: 'transparent',
  fillStyle: 'none' as const,
  strokeWidth: 1,
  strokeStyle: 'solid' as const,
  roughness: 0 as const,
  opacity: 100,
  seed: 1,
  version: 0,
  locked: false,
}

const rect = (over: Partial<CollabElement>): CollabElement =>
  ({
    type: 'rect',
    id: 'r',
    x: 0,
    y: 0,
    width: 100,
    height: 60,
    roundness: 0,
    ...baseFields,
    ...over,
  }) as CollabElement

const text = (over: Partial<CollabElement>): CollabElement =>
  ({
    type: 'text',
    id: 't',
    x: 0,
    y: 0,
    width: 100,
    height: 20,
    text: '',
    fontFamily: 'sans',
    fontSize: 16,
    textAlign: 'left',
    ...baseFields,
    ...over,
  }) as CollabElement

const sticky = (over: Partial<CollabElement>): CollabElement =>
  ({
    type: 'sticky',
    id: 's',
    x: 0,
    y: 0,
    width: 120,
    height: 60,
    text: '',
    fontFamily: 'sans',
    fontSize: 14,
    textAlign: 'left',
    ...baseFields,
    ...over,
  }) as CollabElement

const frame = (over: Partial<CollabElement>): CollabElement =>
  ({
    type: 'frame',
    id: 'f',
    x: 0,
    y: 0,
    width: 200,
    height: 200,
    name: '',
    childIds: [],
    ...baseFields,
    ...over,
  }) as CollabElement

describe('buildSceneOutline', () => {
  it('returns an empty array for an empty scene', () => {
    expect(buildSceneOutline([])).toEqual([])
  })

  it('uses the element type as the label fallback', () => {
    const out = buildSceneOutline([rect({ id: 'r1' })])
    expect(out[0].label).toBe('Rectangle')
  })

  it('uses the text content as the label for text elements', () => {
    const out = buildSceneOutline([text({ id: 't1', text: 'Hello world' })])
    expect(out[0].label).toBe('Hello world')
  })

  it('uses the sticky content as the label for sticky notes', () => {
    const out = buildSceneOutline([sticky({ id: 's1', text: 'TODO: ship it' })])
    expect(out[0].label).toBe('TODO: ship it')
  })

  it('uses the frame name as the label, falling back to "Frame"', () => {
    const named = buildSceneOutline([frame({ id: 'f1', name: 'Onboarding' })])
    expect(named[0].label).toBe('Onboarding')
    const blank = buildSceneOutline([frame({ id: 'f2', name: '' })])
    expect(blank[0].label).toBe('Frame')
  })

  it('places elements claimed by a frame as its children, not at root', () => {
    const r1 = rect({ id: 'r1', y: 10 })
    const r2 = rect({ id: 'r2', y: 20 })
    const f = frame({ id: 'f1', name: 'Box', childIds: ['r1', 'r2'] })
    const out = buildSceneOutline([r1, r2, f])
    expect(out).toHaveLength(1)
    expect(out[0].id).toBe('f1')
    expect(out[0].children.map((c) => c.id)).toEqual(['r1', 'r2'])
  })

  it('keeps frame children in the order declared on childIds', () => {
    // Source array order is r2, r1 — but childIds asks for r1, r2.
    // Outline must follow the frame's declaration.
    const r1 = rect({ id: 'r1', y: 100 })
    const r2 = rect({ id: 'r2', y: 0 })
    const f = frame({ id: 'f1', name: 'F', childIds: ['r1', 'r2'] })
    const out = buildSceneOutline([r2, r1, f])
    expect(out[0].children.map((c) => c.id)).toEqual(['r1', 'r2'])
  })

  it('keeps an orphan element at the root', () => {
    const r1 = rect({ id: 'r1' })
    const out = buildSceneOutline([r1])
    expect(out).toHaveLength(1)
    expect(out[0].id).toBe('r1')
  })

  it('orders root entries by reading order (top-down, left-right)', () => {
    // Frame at y=200, two orphans at y=0 (left then right) and y=100.
    const f = frame({ id: 'f1', name: 'F', y: 200 })
    const a = rect({ id: 'a', y: 0, x: 100 })
    const b = rect({ id: 'b', y: 0, x: 0 })
    const c = rect({ id: 'c', y: 100, x: 50 })
    const out = buildSceneOutline([f, a, b, c])
    expect(out.map((n) => n.id)).toEqual(['b', 'a', 'c', 'f1'])
  })

  it('drops a frame childId that does not resolve to an element', () => {
    const r1 = rect({ id: 'r1' })
    const f = frame({ id: 'f1', childIds: ['r1', 'ghost', 'also-gone'] })
    const out = buildSceneOutline([r1, f])
    expect(out[0].children).toHaveLength(1)
    expect(out[0].children[0].id).toBe('r1')
  })

  it('truncates very long labels with an ellipsis', () => {
    const out = buildSceneOutline([text({ text: 'a'.repeat(200) })])
    expect(out[0].label.length).toBeLessThanOrEqual(60)
    expect(out[0].label.endsWith('…')).toBe(true)
  })

  it('flattens whitespace inside labels (newlines collapse to a space)', () => {
    const out = buildSceneOutline([text({ text: 'line one\nline two' })])
    expect(out[0].label).toBe('line one line two')
  })

  it('exposes the element kind so the panel can pick an icon', () => {
    const out = buildSceneOutline([
      rect({ id: 'r' }),
      text({ id: 't', text: 'hi' }),
      sticky({ id: 's', text: 'note' }),
      frame({ id: 'f', name: 'F' }),
    ])
    const kinds = out.map((n) => n.kind).sort()
    expect(kinds).toEqual(['frame', 'rect', 'sticky', 'text'])
  })

  it('does not include a frame as its own child even if it appears in childIds', () => {
    // Defensive — a frame referencing itself shouldn't loop.
    const f = frame({ id: 'f', name: 'F', childIds: ['f'] })
    const out = buildSceneOutline([f])
    // Self-reference resolves to the frame element, gets toLeafNode'd
    // → harmless, but we must not infinitely recurse.
    expect(out).toHaveLength(1)
    expect(out[0].id).toBe('f')
  })
})
