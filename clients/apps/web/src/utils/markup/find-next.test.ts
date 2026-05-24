import { afterEach, beforeEach, describe, expect, it } from 'vitest'

import type { CollabElement } from './elements'
import {
  _resetFindStateForTests,
  findNext,
  findPrevious,
  hasActiveSearch,
  recordSearchPick,
} from './find-next'

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

const text = (id: string, text: string, y = 0): CollabElement =>
  ({
    type: 'text',
    id,
    x: 0,
    y,
    width: 100,
    height: 20,
    text,
    fontFamily: 'sans',
    fontSize: 16,
    textAlign: 'left',
    ...baseFields,
  }) as CollabElement

const elements = [
  text('a', 'Apple', 0),
  text('b', 'Apple pie', 100),
  text('c', 'Apple sauce', 200),
  text('d', 'Banana', 300),
]

beforeEach(() => {
  _resetFindStateForTests()
})

afterEach(() => {
  _resetFindStateForTests()
})

describe('hasActiveSearch', () => {
  it('false initially', () => {
    expect(hasActiveSearch()).toBe(false)
  })

  it('true after a search has been recorded', () => {
    recordSearchPick('apple', 'a')
    expect(hasActiveSearch()).toBe(true)
  })
})

describe('findNext', () => {
  it('returns null when no search has been recorded', () => {
    expect(findNext(elements)).toBeNull()
  })

  it('returns the next hit in the cached query', () => {
    recordSearchPick('apple', 'a')
    const next = findNext(elements)
    expect(next?.elementId).toBe('b')
  })

  it('wraps to the first hit when the cursor is on the last', () => {
    recordSearchPick('apple', 'c')
    expect(findNext(elements)?.elementId).toBe('a')
  })

  it('advances the cursor so a second call returns the one after that', () => {
    recordSearchPick('apple', 'a')
    findNext(elements) // → b
    const after = findNext(elements)
    expect(after?.elementId).toBe('c')
  })

  it('returns the first hit when the last picked id is no longer in the result set', () => {
    recordSearchPick('apple', 'gone')
    expect(findNext(elements)?.elementId).toBe('a')
  })

  it('returns null when the cached query has no hits in the live scene', () => {
    recordSearchPick('mango', 'a')
    expect(findNext(elements)).toBeNull()
  })
})

describe('findPrevious', () => {
  it('returns null when no search has been recorded', () => {
    expect(findPrevious(elements)).toBeNull()
  })

  it('returns the previous hit in the cached query', () => {
    recordSearchPick('apple', 'b')
    expect(findPrevious(elements)?.elementId).toBe('a')
  })

  it('wraps to the last hit when the cursor is on the first', () => {
    recordSearchPick('apple', 'a')
    expect(findPrevious(elements)?.elementId).toBe('c')
  })

  it('returns the last hit when the cursor was on a now-missing id', () => {
    recordSearchPick('apple', 'gone')
    expect(findPrevious(elements)?.elementId).toBe('c')
  })
})

describe('cursor advancement after a step', () => {
  it('chained next + previous round-trips', () => {
    recordSearchPick('apple', 'a')
    expect(findNext(elements)?.elementId).toBe('b')
    expect(findPrevious(elements)?.elementId).toBe('a')
  })
})
