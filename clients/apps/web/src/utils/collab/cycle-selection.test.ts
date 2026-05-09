import { describe, expect, it } from 'vitest'

import { cycleNext, cyclePrev } from './cycle-selection'
import type { CollabElement } from './elements'

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

const rect = (
  id: string,
  x: number,
  y: number,
  over: object = {},
): CollabElement =>
  ({
    type: 'rect',
    id,
    x,
    y,
    width: 10,
    height: 10,
    roundness: 0,
    ...baseFields,
    ...over,
  }) as CollabElement

describe('cycleNext', () => {
  it('returns null when there are no eligible elements', () => {
    expect(cycleNext([], null)).toBeNull()
  })

  it('returns the first element in reading order with no current id', () => {
    const elements = [rect('a', 0, 100), rect('b', 0, 0), rect('c', 0, 200)]
    // y sorts: b (0), a (100), c (200) → first is b.
    expect(cycleNext(elements, null)).toBe('b')
  })

  it('returns the next element after currentId', () => {
    const elements = [rect('a', 0, 0), rect('b', 0, 100), rect('c', 0, 200)]
    expect(cycleNext(elements, 'a')).toBe('b')
    expect(cycleNext(elements, 'b')).toBe('c')
  })

  it('wraps to the first element after the last', () => {
    const elements = [rect('a', 0, 0), rect('b', 0, 100)]
    expect(cycleNext(elements, 'b')).toBe('a')
  })

  it('breaks ties by left-right of centre X', () => {
    const elements = [rect('right', 100, 0), rect('left', 0, 0)]
    expect(cycleNext(elements, null)).toBe('left')
    expect(cycleNext(elements, 'left')).toBe('right')
  })

  it('falls back to the first when currentId is missing from the scene', () => {
    const elements = [rect('a', 0, 0), rect('b', 0, 100)]
    expect(cycleNext(elements, 'ghost')).toBe('a')
  })

  it('skips hidden elements', () => {
    const elements = [
      rect('a', 0, 0),
      rect('b', 0, 100, { hidden: true }),
      rect('c', 0, 200),
    ]
    expect(cycleNext(elements, 'a')).toBe('c')
  })

  it('skips locked elements', () => {
    const elements = [
      rect('a', 0, 0),
      rect('b', 0, 100, { locked: true }),
      rect('c', 0, 200),
    ]
    expect(cycleNext(elements, 'a')).toBe('c')
  })

  it('returns null when every element is hidden / locked', () => {
    const elements = [
      rect('a', 0, 0, { hidden: true }),
      rect('b', 0, 100, { locked: true }),
    ]
    expect(cycleNext(elements, null)).toBeNull()
  })
})

describe('cyclePrev', () => {
  it('returns the last element in reading order with no current id', () => {
    const elements = [rect('a', 0, 0), rect('b', 0, 100), rect('c', 0, 200)]
    expect(cyclePrev(elements, null)).toBe('c')
  })

  it('returns the previous element', () => {
    const elements = [rect('a', 0, 0), rect('b', 0, 100), rect('c', 0, 200)]
    expect(cyclePrev(elements, 'c')).toBe('b')
    expect(cyclePrev(elements, 'b')).toBe('a')
  })

  it('wraps to the last element when currentId is the first', () => {
    const elements = [rect('a', 0, 0), rect('b', 0, 100)]
    expect(cyclePrev(elements, 'a')).toBe('b')
  })

  it('falls back to the last when currentId is missing', () => {
    const elements = [rect('a', 0, 0), rect('b', 0, 100)]
    expect(cyclePrev(elements, 'ghost')).toBe('b')
  })
})

describe('round-trip', () => {
  it('next + prev returns the original currentId', () => {
    const elements = [rect('a', 0, 0), rect('b', 0, 100), rect('c', 0, 200)]
    const after = cycleNext(elements, 'a')!
    expect(cyclePrev(elements, after)).toBe('a')
  })
})
