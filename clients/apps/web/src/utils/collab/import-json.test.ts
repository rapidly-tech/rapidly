/**
 * JSON import — pinned behaviour:
 *
 * - ``parseExportedScene`` accepts a string or a pre-parsed object.
 * - Wrong schema / wrong version / non-array elements → typed error.
 * - ``importScene`` mints fresh ids by default (re-import → no collision).
 * - ``preserveIds`` reuses the original ids (round-trip).
 * - ``offset`` translates every imported element by the same delta.
 * - One Yjs transaction → one undo step.
 */

import { describe, expect, it } from 'vitest'
import * as Y from 'yjs'

import { createElementStore } from './element-store'
import { exportToJSON } from './export'
import { importScene, isImportError, parseExportedScene } from './import-json'

describe('parseExportedScene', () => {
  it('accepts a JSON string', () => {
    const json = JSON.stringify({
      schema: 'rapidly-collab-v1',
      version: 1,
      elements: [],
    })
    const result = parseExportedScene(json)
    expect(isImportError(result)).toBe(false)
  })

  it('accepts a pre-parsed object', () => {
    const result = parseExportedScene({
      schema: 'rapidly-collab-v1',
      version: 1,
      elements: [],
    })
    expect(isImportError(result)).toBe(false)
  })

  it('rejects malformed JSON strings', () => {
    const result = parseExportedScene('{not json')
    expect(isImportError(result)).toBe(true)
    if (isImportError(result)) {
      expect(result.reason).toBe('invalid-json')
    }
  })

  it('rejects non-object payloads', () => {
    expect(isImportError(parseExportedScene('null'))).toBe(true)
    expect(isImportError(parseExportedScene(42))).toBe(true)
    expect(isImportError(parseExportedScene([]))).toBe(true) // arrays fail schema check
  })

  it('rejects wrong schema marker', () => {
    const result = parseExportedScene({
      schema: 'excalidraw',
      version: 1,
      elements: [],
    })
    expect(isImportError(result) && result.reason).toBe('wrong-schema')
  })

  it('rejects wrong version', () => {
    const result = parseExportedScene({
      schema: 'rapidly-collab-v1',
      version: 2,
      elements: [],
    })
    expect(isImportError(result) && result.reason).toBe('wrong-version')
  })

  it('rejects missing or non-array elements', () => {
    const result = parseExportedScene({
      schema: 'rapidly-collab-v1',
      version: 1,
      elements: 'oops',
    })
    expect(isImportError(result) && result.reason).toBe('missing-elements')
  })
})

describe('importScene', () => {
  it('round-trips an exported scene', () => {
    const docA = new Y.Doc()
    const a = createElementStore(docA)
    a.create({ id: 'src', type: 'rect', x: 10, y: 20, width: 30, height: 40 })

    const scene = exportToJSON(a.list())

    const docB = new Y.Doc()
    const b = createElementStore(docB)
    const newIds = importScene(b, scene)

    expect(newIds).toHaveLength(1)
    const imported = b.get(newIds[0])
    expect(imported?.x).toBe(10)
    expect(imported?.width).toBe(30)
    // Fresh id by default — should differ from the original.
    expect(newIds[0]).not.toBe('src')
  })

  it('preserves original ids when preserveIds=true', () => {
    const doc = new Y.Doc()
    const store = createElementStore(doc)
    const scene = parseExportedScene({
      schema: 'rapidly-collab-v1',
      version: 1,
      elements: [
        {
          id: 'frozen',
          type: 'rect',
          x: 0,
          y: 0,
          width: 10,
          height: 10,
          angle: 0,
          zIndex: 0,
          groupIds: [],
          strokeColor: '#000',
          fillColor: 'transparent',
          fillStyle: 'solid',
          strokeWidth: 1,
          strokeStyle: 'solid',
          roughness: 0,
          opacity: 1,
          seed: 1,
          version: 1,
          locked: false,
        },
      ],
    })
    if (isImportError(scene)) throw new Error('parse failed')
    const ids = importScene(store, scene, { preserveIds: true })
    expect(ids).toEqual(['frozen'])
    expect(store.get('frozen')).not.toBeNull()
  })

  it('applies the offset to every imported element', () => {
    const doc = new Y.Doc()
    const store = createElementStore(doc)
    const sourceDoc = new Y.Doc()
    const source = createElementStore(sourceDoc)
    source.create({ id: 'a', type: 'rect', x: 0, y: 0, width: 20, height: 20 })
    source.create({
      id: 'b',
      type: 'rect',
      x: 50,
      y: 30,
      width: 20,
      height: 20,
    })

    const scene = exportToJSON(source.list())
    const ids = importScene(store, scene, { offset: { x: 100, y: 200 } })
    const [first, second] = ids.map((id) => store.get(id)!)
    // Offsets applied uniformly.
    expect(first.x - 0).toBe(100)
    expect(first.y - 0).toBe(200)
    expect(second.x - 50).toBe(100)
    expect(second.y - 30).toBe(200)
  })

  it('runs the whole import in a single Yjs transaction', () => {
    const doc = new Y.Doc()
    const store = createElementStore(doc)
    const sourceDoc = new Y.Doc()
    const source = createElementStore(sourceDoc)
    source.create({ id: 'a', type: 'rect', x: 0, y: 0, width: 20, height: 20 })
    source.create({ id: 'b', type: 'rect', x: 1, y: 1, width: 20, height: 20 })
    source.create({ id: 'c', type: 'rect', x: 2, y: 2, width: 20, height: 20 })

    const scene = exportToJSON(source.list())
    let txCount = 0
    doc.on('afterTransaction', () => {
      txCount++
    })
    importScene(store, scene)
    expect(txCount).toBe(1)
  })

  it('returns an empty array for an empty scene', () => {
    const doc = new Y.Doc()
    const store = createElementStore(doc)
    const scene = parseExportedScene({
      schema: 'rapidly-collab-v1',
      version: 1,
      elements: [],
    })
    if (isImportError(scene)) throw new Error('parse failed')
    expect(importScene(store, scene)).toEqual([])
    expect(store.size).toBe(0)
  })
})
