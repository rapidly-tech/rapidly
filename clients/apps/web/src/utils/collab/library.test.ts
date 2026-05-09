import { describe, expect, it } from 'vitest'

import {
  deleteTemplate,
  LIBRARY_STORAGE_KEY,
  listTemplates,
  saveTemplate,
} from './library'

/** Tiny in-memory ``Storage`` shim so tests don't need jsdom's
 *  localStorage. Behaves like the real thing for the methods
 *  ``library`` actually calls. */
function makeStorage(): Storage {
  const map = new Map<string, string>()
  return {
    getItem: (k) => map.get(k) ?? null,
    setItem: (k, v) => {
      map.set(k, v)
    },
    removeItem: (k) => {
      map.delete(k)
    },
    clear: () => map.clear(),
    key: (i) => Array.from(map.keys())[i] ?? null,
    get length() {
      return map.size
    },
  } as Storage
}

const sampleEls = [
  {
    type: 'rect',
    x: 100,
    y: 200,
    width: 50,
    height: 30,
    strokeColor: '#000',
    seed: 1,
  },
  {
    type: 'ellipse',
    x: 160,
    y: 200,
    width: 40,
    height: 30,
    strokeColor: '#000',
    seed: 2,
  },
]

describe('listTemplates', () => {
  it('returns empty when storage is empty', () => {
    expect(listTemplates(makeStorage())).toEqual([])
  })

  it('returns empty when stored data is malformed JSON', () => {
    const storage = makeStorage()
    storage.setItem(LIBRARY_STORAGE_KEY, '{not json')
    expect(listTemplates(storage)).toEqual([])
  })

  it('returns empty when the schema marker is missing or wrong', () => {
    const storage = makeStorage()
    storage.setItem(
      LIBRARY_STORAGE_KEY,
      JSON.stringify({ schema: 'wrong', templates: [{ id: 'x' }] }),
    )
    expect(listTemplates(storage)).toEqual([])
  })
})

describe('saveTemplate', () => {
  it('rejects an empty name', () => {
    const storage = makeStorage()
    expect(saveTemplate('   ', sampleEls, storage)).toBeNull()
    expect(listTemplates(storage)).toEqual([])
  })

  it('rejects an empty element list', () => {
    const storage = makeStorage()
    expect(saveTemplate('Logo', [], storage)).toBeNull()
    expect(listTemplates(storage)).toEqual([])
  })

  it('persists a template with normalised template-local coordinates', () => {
    const storage = makeStorage()
    const saved = saveTemplate('Pair', sampleEls, storage)
    expect(saved).not.toBeNull()
    expect(saved!.name).toBe('Pair')
    // Selection AABB: x 100..200 (width 100), y 200..230 (height 30).
    expect(saved!.width).toBe(100)
    expect(saved!.height).toBe(30)
    // Top-left element should now sit at (0, 0).
    const rect = saved!.elements[0] as { x: number; y: number }
    expect(rect.x).toBe(0)
    expect(rect.y).toBe(0)
    // Second element keeps its relative offset.
    const ellipse = saved!.elements[1] as { x: number; y: number }
    expect(ellipse.x).toBe(60)
    expect(ellipse.y).toBe(0)
  })

  it('strips ids on save so reinserts mint fresh ones', () => {
    const storage = makeStorage()
    const saved = saveTemplate(
      'WithId',
      [{ ...sampleEls[0], id: 'old-id' }],
      storage,
    )
    expect(saved!.elements[0].id).toBeUndefined()
  })

  it('preserves seed + style fields exactly', () => {
    const storage = makeStorage()
    const saved = saveTemplate('Styled', sampleEls, storage)
    const out = saved!.elements[0] as Record<string, unknown>
    expect(out.seed).toBe(1)
    expect(out.strokeColor).toBe('#000')
    expect(out.type).toBe('rect')
  })

  it('newest-first ordering', () => {
    const storage = makeStorage()
    saveTemplate('First', sampleEls, storage)
    saveTemplate('Second', sampleEls, storage)
    const list = listTemplates(storage)
    expect(list.map((t) => t.name)).toEqual(['Second', 'First'])
  })
})

describe('deleteTemplate', () => {
  it('removes a template by id', () => {
    const storage = makeStorage()
    const a = saveTemplate('A', sampleEls, storage)!
    const b = saveTemplate('B', sampleEls, storage)!
    deleteTemplate(a.id, storage)
    const remaining = listTemplates(storage)
    expect(remaining.map((t) => t.id)).toEqual([b.id])
  })

  it('is a no-op for an unknown id', () => {
    const storage = makeStorage()
    saveTemplate('A', sampleEls, storage)
    deleteTemplate('does-not-exist', storage)
    expect(listTemplates(storage)).toHaveLength(1)
  })
})
