import { describe, expect, it } from 'vitest'
import * as Y from 'yjs'

import { createElementStore } from './element-store'
import {
  exportFrameAsJson,
  exportFrameAsPng,
  exportFrameAsSvg,
  frameDescendants,
} from './frame-export'

const baseRect = {
  type: 'rect' as const,
  x: 0,
  y: 0,
  width: 100,
  height: 60,
  roundness: 0,
}

const baseFrame = (childIds: string[] = []) => ({
  type: 'frame' as const,
  x: 0,
  y: 0,
  width: 200,
  height: 200,
  name: 'Test frame',
  childIds,
})

describe('frameDescendants', () => {
  it('returns an empty array when the frame id is unknown', () => {
    const doc = new Y.Doc()
    const store = createElementStore(doc)
    expect(frameDescendants(store, 'nope')).toEqual([])
  })

  it('returns an empty array when the id resolves to a non-frame element', () => {
    const doc = new Y.Doc()
    const store = createElementStore(doc)
    const id = store.create(baseRect)
    expect(frameDescendants(store, id)).toEqual([])
  })

  it('returns just the frame when it has no children', () => {
    const doc = new Y.Doc()
    const store = createElementStore(doc)
    const frameId = store.create(baseFrame([]))
    const result = frameDescendants(store, frameId)
    expect(result).toHaveLength(1)
    expect(result[0].id).toBe(frameId)
  })

  it('returns the frame followed by every child in childIds order', () => {
    const doc = new Y.Doc()
    const store = createElementStore(doc)
    const a = store.create(baseRect)
    const b = store.create(baseRect)
    const c = store.create(baseRect)
    const frameId = store.create(baseFrame([c, a, b]))
    const result = frameDescendants(store, frameId)
    // Frame first, then children in childIds order (c, a, b).
    expect(result.map((e) => e.id)).toEqual([frameId, c, a, b])
  })

  it('skips childIds that no longer resolve in the store', () => {
    const doc = new Y.Doc()
    const store = createElementStore(doc)
    const a = store.create(baseRect)
    const frameId = store.create(baseFrame([a, 'ghost-1', 'ghost-2']))
    const result = frameDescendants(store, frameId)
    expect(result.map((e) => e.id)).toEqual([frameId, a])
  })
})

describe('exportFrameAsPng', () => {
  it('returns null when the frame id is unknown', async () => {
    const doc = new Y.Doc()
    const store = createElementStore(doc)
    expect(await exportFrameAsPng(store, 'missing')).toBeNull()
  })

  it('returns null when the id resolves to a non-frame element', async () => {
    // The frame-only guard lives in ``frameDescendants`` and the
    // wrapper short-circuits when that returns no elements; verify
    // the path without asking jsdom to actually rasterise.
    const doc = new Y.Doc()
    const store = createElementStore(doc)
    const id = store.create(baseRect)
    expect(await exportFrameAsPng(store, id)).toBeNull()
  })
})

describe('exportFrameAsSvg', () => {
  it('returns null when the frame id is unknown', () => {
    const doc = new Y.Doc()
    const store = createElementStore(doc)
    expect(exportFrameAsSvg(store, 'missing')).toBeNull()
  })

  it('returns null when the id resolves to a non-frame element', () => {
    const doc = new Y.Doc()
    const store = createElementStore(doc)
    const id = store.create(baseRect)
    expect(exportFrameAsSvg(store, id)).toBeNull()
  })

  it('returns an SVG string for a real frame', () => {
    const doc = new Y.Doc()
    const store = createElementStore(doc)
    const a = store.create(baseRect)
    const frameId = store.create(baseFrame([a]))
    const svg = exportFrameAsSvg(store, frameId)
    expect(svg).toBeTypeOf('string')
    expect(svg).toContain('<svg')
    expect(svg).toContain('</svg>')
  })
})

describe('exportFrameAsJson', () => {
  it('returns null when the frame id is unknown', () => {
    const doc = new Y.Doc()
    const store = createElementStore(doc)
    expect(exportFrameAsJson(store, 'missing')).toBeNull()
  })

  it('returns null when the id resolves to a non-frame element', () => {
    const doc = new Y.Doc()
    const store = createElementStore(doc)
    const id = store.create(baseRect)
    expect(exportFrameAsJson(store, id)).toBeNull()
  })

  it('returns the versioned envelope with frame + children', () => {
    const doc = new Y.Doc()
    const store = createElementStore(doc)
    const a = store.create(baseRect)
    const b = store.create(baseRect)
    const frameId = store.create(baseFrame([a, b]))
    const scene = exportFrameAsJson(store, frameId)
    expect(scene).not.toBeNull()
    expect(scene!.elements.map((e) => e.id)).toEqual([frameId, a, b])
    expect(scene!.schema).toBe('rapidly-collab-v1')
  })
})
