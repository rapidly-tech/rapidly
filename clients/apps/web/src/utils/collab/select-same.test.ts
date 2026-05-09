import { describe, expect, it } from 'vitest'
import * as Y from 'yjs'

import { createElementStore } from './element-store'
import {
  selectSameFillColor,
  selectSameFontFamily,
  selectSameStrokeColor,
  selectSameType,
} from './select-same'

const baseRect = (over: object = {}) => ({
  type: 'rect' as const,
  x: 0,
  y: 0,
  width: 10,
  height: 10,
  roundness: 0,
  strokeColor: '#1e1e1e',
  fillColor: 'transparent',
  ...over,
})

const baseEllipse = (over: object = {}) => ({
  type: 'ellipse' as const,
  x: 0,
  y: 0,
  width: 10,
  height: 10,
  strokeColor: '#1e1e1e',
  fillColor: 'transparent',
  ...over,
})

const baseText = (over: object = {}) => ({
  type: 'text' as const,
  x: 0,
  y: 0,
  width: 100,
  height: 20,
  text: 'hello',
  fontFamily: 'sans' as const,
  fontSize: 16,
  textAlign: 'left' as const,
  strokeColor: '#1e1e1e',
  ...over,
})

describe('selectSameType', () => {
  it('returns every element of the seed s type', () => {
    const doc = new Y.Doc()
    const store = createElementStore(doc)
    const r1 = store.create(baseRect())
    const r2 = store.create(baseRect())
    store.create(baseEllipse())
    expect(selectSameType(store, new Set([r1])).sort()).toEqual([r1, r2].sort())
  })

  it('returns an empty array when the seed selection is empty', () => {
    const doc = new Y.Doc()
    const store = createElementStore(doc)
    store.create(baseRect())
    expect(selectSameType(store, new Set())).toEqual([])
  })

  it('skips ids that no longer resolve in the store', () => {
    const doc = new Y.Doc()
    const store = createElementStore(doc)
    const r = store.create(baseRect())
    expect(selectSameType(store, new Set(['ghost', r])).sort()).toEqual([r])
  })
})

describe('selectSameStrokeColor', () => {
  it('matches across types — strokeColor cuts through type boundaries', () => {
    const doc = new Y.Doc()
    const store = createElementStore(doc)
    const r = store.create(baseRect({ strokeColor: '#ff0000' }))
    const e = store.create(baseEllipse({ strokeColor: '#ff0000' }))
    store.create(baseRect({ strokeColor: '#00ff00' }))
    expect(selectSameStrokeColor(store, new Set([r])).sort()).toEqual(
      [r, e].sort(),
    )
  })

  it('returns just the seed when no other element shares the colour', () => {
    const doc = new Y.Doc()
    const store = createElementStore(doc)
    const r = store.create(baseRect({ strokeColor: '#ff0000' }))
    store.create(baseRect({ strokeColor: '#00ff00' }))
    expect(selectSameStrokeColor(store, new Set([r]))).toEqual([r])
  })
})

describe('selectSameFillColor', () => {
  it('matches across types and respects transparent fills', () => {
    const doc = new Y.Doc()
    const store = createElementStore(doc)
    const a = store.create(baseRect({ fillColor: 'transparent' }))
    const b = store.create(baseEllipse({ fillColor: 'transparent' }))
    store.create(baseRect({ fillColor: '#a5d8ff' }))
    expect(selectSameFillColor(store, new Set([a])).sort()).toEqual(
      [a, b].sort(),
    )
  })
})

describe('selectSameFontFamily', () => {
  it('returns every text / sticky / etc. element sharing the font', () => {
    const doc = new Y.Doc()
    const store = createElementStore(doc)
    const a = store.create(baseText({ fontFamily: 'mono' }))
    const b = store.create(baseText({ fontFamily: 'mono' }))
    store.create(baseText({ fontFamily: 'sans' }))
    expect(selectSameFontFamily(store, new Set([a])).sort()).toEqual(
      [a, b].sort(),
    )
  })

  it('returns [] when the seed has no font (rect / ellipse / arrow)', () => {
    const doc = new Y.Doc()
    const store = createElementStore(doc)
    const r = store.create(baseRect())
    store.create(baseText())
    expect(selectSameFontFamily(store, new Set([r]))).toEqual([])
  })
})

describe('seed-resolution policy', () => {
  it('uses the first valid seed id (later seeds + ghosts ignored)', () => {
    const doc = new Y.Doc()
    const store = createElementStore(doc)
    const r = store.create(baseRect({ strokeColor: '#ff0000' }))
    const e = store.create(baseEllipse({ strokeColor: '#00ff00' }))
    // First valid id wins → red wins; only the rect comes back.
    expect(selectSameStrokeColor(store, new Set([r, e])).sort()).toEqual([r])
  })
})
