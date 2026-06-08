import { describe, expect, it } from 'vitest'
import * as Y from 'yjs'

import { displayName, setName } from './element-name'
import { createElementStore } from './element-store'
import type { CollabElement } from './elements'

const baseRect = {
  type: 'rect' as const,
  x: 0,
  y: 0,
  width: 100,
  height: 60,
  roundness: 0,
}

const baseFrame = {
  type: 'frame' as const,
  x: 0,
  y: 0,
  width: 200,
  height: 200,
  name: 'Original',
  childIds: [] as string[],
}

const baseText = {
  type: 'text' as const,
  x: 0,
  y: 0,
  width: 100,
  height: 20,
  text: 'Hello',
  fontFamily: 'sans' as const,
  fontSize: 16,
  textAlign: 'left' as const,
}

describe('setName', () => {
  it('writes the name to a non-frame element', () => {
    const doc = new Y.Doc()
    const store = createElementStore(doc)
    const id = store.create(baseRect)
    setName(store, new Set([id]), 'Login button')
    expect((store.get(id) as { name?: string }).name).toBe('Login button')
  })

  it('overwrites a frame element s built-in label', () => {
    const doc = new Y.Doc()
    const store = createElementStore(doc)
    const id = store.create(baseFrame)
    setName(store, new Set([id]), 'Onboarding flow')
    expect((store.get(id) as { name: string }).name).toBe('Onboarding flow')
  })

  it('trims surrounding whitespace', () => {
    const doc = new Y.Doc()
    const store = createElementStore(doc)
    const id = store.create(baseRect)
    setName(store, new Set([id]), '   Spaced   ')
    expect((store.get(id) as { name?: string }).name).toBe('Spaced')
  })

  it('clears the name on a non-frame element when given an empty string', () => {
    const doc = new Y.Doc()
    const store = createElementStore(doc)
    const id = store.create({ ...baseRect, name: 'Will be cleared' })
    setName(store, new Set([id]), '')
    expect((store.get(id) as { name?: string }).name).toBeUndefined()
  })

  it('clears a frame label to empty string (frame requires the field)', () => {
    const doc = new Y.Doc()
    const store = createElementStore(doc)
    const id = store.create(baseFrame)
    setName(store, new Set([id]), '   ')
    expect((store.get(id) as { name: string }).name).toBe('')
  })

  it('applies the same name to every element in the selection', () => {
    const doc = new Y.Doc()
    const store = createElementStore(doc)
    const a = store.create(baseRect)
    const b = store.create(baseRect)
    setName(store, new Set([a, b]), 'Pair')
    expect((store.get(a) as { name?: string }).name).toBe('Pair')
    expect((store.get(b) as { name?: string }).name).toBe('Pair')
  })

  it('is a no-op for an empty selection', () => {
    const doc = new Y.Doc()
    const store = createElementStore(doc)
    const id = store.create({ ...baseRect, name: 'Keep me' })
    setName(store, new Set(), 'Should not apply')
    expect((store.get(id) as { name?: string }).name).toBe('Keep me')
  })

  it('skips ids that are not in the store', () => {
    const doc = new Y.Doc()
    const store = createElementStore(doc)
    const id = store.create(baseRect)
    expect(() =>
      setName(store, new Set([id, 'ghost']), 'Survives the ghost'),
    ).not.toThrow()
    expect((store.get(id) as { name?: string }).name).toBe('Survives the ghost')
  })
})

describe('displayName', () => {
  it('returns the explicit name when set', () => {
    const el = {
      ...baseRect,
      id: 'x',
      name: 'My rect',
    } as unknown as CollabElement
    expect(displayName(el)).toBe('My rect')
  })

  it('falls back to a humanised type when no name is set', () => {
    const cases: Array<[CollabElement['type'], string]> = [
      ['rect', 'Rectangle'],
      ['ellipse', 'Ellipse'],
      ['diamond', 'Diamond'],
      ['arrow', 'Arrow'],
      ['line', 'Line'],
      ['freedraw', 'Drawing'],
      ['text', 'Text'],
      ['sticky', 'Sticky note'],
      ['image', 'Image'],
      ['embed', 'Embed'],
    ]
    for (const [type, expected] of cases) {
      const el = { type, id: 'x' } as unknown as CollabElement
      expect(displayName(el)).toBe(expected)
    }
  })

  it('returns the frame label when set, falls back to "Frame" when blank', () => {
    const named = {
      type: 'frame',
      id: 'f',
      name: 'Hero',
    } as unknown as CollabElement
    expect(displayName(named)).toBe('Hero')
    const blank = {
      type: 'frame',
      id: 'f',
      name: '',
    } as unknown as CollabElement
    expect(displayName(blank)).toBe('Frame')
  })

  it('treats whitespace-only names as unset', () => {
    const el = { ...baseRect, id: 'x', name: '   ' } as unknown as CollabElement
    expect(displayName(el)).toBe('Rectangle')
  })

  it('trims a valid name before returning it', () => {
    const el = {
      ...baseText,
      id: 'x',
      name: '   trimmed   ',
    } as unknown as CollabElement
    expect(displayName(el)).toBe('trimmed')
  })
})
