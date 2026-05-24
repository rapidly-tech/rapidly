import { describe, expect, it } from 'vitest'

import type { CollabElement } from './elements'
import { searchScene } from './scene-search'

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

const embed = (over: Partial<CollabElement>): CollabElement =>
  ({
    type: 'embed',
    id: 'e',
    x: 0,
    y: 0,
    width: 320,
    height: 240,
    url: '',
    sandbox: '',
    ...baseFields,
    ...over,
  }) as CollabElement

describe('searchScene', () => {
  it('returns no hits for an empty query', () => {
    expect(searchScene([text({ text: 'Hello' })], '')).toEqual([])
    expect(searchScene([text({ text: 'Hello' })], '   ')).toEqual([])
  })

  it('returns no hits when nothing matches', () => {
    const hits = searchScene([text({ text: 'Hello' })], 'goodbye')
    expect(hits).toEqual([])
  })

  it('finds a substring match in a text element', () => {
    const hits = searchScene([text({ text: 'Welcome aboard' })], 'come')
    expect(hits).toHaveLength(1)
    expect(hits[0].elementId).toBe('t')
    expect(hits[0].kind).toBe('text')
  })

  it('matches case-insensitively', () => {
    const hits = searchScene([text({ text: 'Onboarding' })], 'ONBOARD')
    expect(hits).toHaveLength(1)
  })

  it('finds matches in sticky notes', () => {
    const hits = searchScene([sticky({ text: 'TODO: write tests' })], 'tests')
    expect(hits[0].kind).toBe('sticky')
  })

  it('finds matches in frame names', () => {
    const hits = searchScene([frame({ name: 'Onboarding flow' })], 'flow')
    expect(hits[0].kind).toBe('frame')
  })

  it('finds matches in embed URLs', () => {
    const hits = searchScene(
      [embed({ url: 'https://www.youtube.com/watch?v=abc' })],
      'youtube',
    )
    expect(hits[0].kind).toBe('embed')
  })

  it('attributes a hit to the parent shape when the text is bound', () => {
    const child = text({ id: 'child', text: 'Place order' })
    const parent = rect({ id: 'parent', boundTextId: 'child' })
    const hits = searchScene([child, parent], 'order')
    expect(hits).toHaveLength(1)
    expect(hits[0].elementId).toBe('parent')
    expect(hits[0].kind).toBe('rect label')
  })

  it('orders an exact match above a substring match', () => {
    const a = text({ id: 'a', text: 'order' }) // exact
    const b = text({ id: 'b', text: 'reorder pile' }) // substring
    const hits = searchScene([a, b], 'order')
    expect(hits.map((h) => h.elementId)).toEqual(['a', 'b'])
  })

  it('orders a whole-word match above a substring match', () => {
    const a = text({ id: 'a', text: 'place the order now' }) // whole word
    const b = text({ id: 'b', text: 'reorderable' }) // substring
    const hits = searchScene([a, b], 'order')
    expect(hits[0].elementId).toBe('a')
  })

  it('orders a prefix match above a non-prefix substring', () => {
    const a = text({ id: 'a', text: 'orderable' }) // prefix
    const b = text({ id: 'b', text: 'reorderable' }) // substring
    const hits = searchScene([a, b], 'order')
    expect(hits[0].elementId).toBe('a')
  })

  it('breaks ties by reading order (top-down then left-right)', () => {
    const a = text({ id: 'a', text: 'order', x: 100, y: 200 })
    const b = text({ id: 'b', text: 'order', x: 0, y: 100 })
    const c = text({ id: 'c', text: 'order', x: 200, y: 100 })
    const hits = searchScene([a, b, c], 'order')
    expect(hits.map((h) => h.elementId)).toEqual(['b', 'c', 'a'])
  })

  it('caps results at the supplied limit', () => {
    const elements = Array.from({ length: 50 }, (_, i) =>
      text({ id: `t${i}`, text: 'order', y: i }),
    )
    const hits = searchScene(elements, 'order', 10)
    expect(hits).toHaveLength(10)
  })

  it('returns the centre of the target element for viewport panning', () => {
    const hits = searchScene(
      [text({ text: 'Hi', x: 100, y: 200, width: 60, height: 20 })],
      'hi',
    )
    expect(hits[0].centerX).toBe(130)
    expect(hits[0].centerY).toBe(210)
  })

  it('builds a snippet with leading/trailing ellipses when match is mid-string', () => {
    const longText = 'a'.repeat(80) + 'needle' + 'b'.repeat(80)
    const hits = searchScene([text({ text: longText })], 'needle')
    expect(hits[0].snippet.startsWith('…')).toBe(true)
    expect(hits[0].snippet.endsWith('…')).toBe(true)
    expect(hits[0].snippet).toContain('needle')
  })

  it('does NOT add ellipses when the match is at the start or end', () => {
    const hits = searchScene([text({ text: 'needle in haystack' })], 'needle')
    expect(hits[0].snippet.startsWith('…')).toBe(false)
  })

  it('skips text elements with empty text', () => {
    const hits = searchScene([text({ text: '' })], 'anything')
    expect(hits).toEqual([])
  })

  it('escapes regex metacharacters in the query', () => {
    const hits = searchScene(
      [text({ text: 'price is $5.00 (tax included)' })],
      '$5.00',
    )
    expect(hits).toHaveLength(1)
  })

  it('deduplicates hits across multiple haystacks for the same element', () => {
    // The parent has bound text matching, AND if both attribution
    // paths fired we'd get two rows; we should only keep the best.
    const child = text({ id: 'child', text: 'order order' })
    const parent = rect({ id: 'parent', boundTextId: 'child' })
    const hits = searchScene([child, parent], 'order')
    expect(hits.filter((h) => h.elementId === 'parent')).toHaveLength(1)
  })
})
