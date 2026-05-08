import { describe, expect, it } from 'vitest'
import * as Y from 'yjs'

import { createElementStore } from './element-store'
import { swapStrokeAndFill } from './swap-colors'

const baseRect = (over: object = {}) => ({
  type: 'rect' as const,
  x: 0,
  y: 0,
  width: 10,
  height: 10,
  roundness: 0,
  strokeColor: '#1e1e1e',
  fillColor: '#a5d8ff',
  fillStyle: 'solid' as const,
  ...over,
})

describe('swapStrokeAndFill', () => {
  it('swaps the two colour fields', () => {
    const doc = new Y.Doc()
    const store = createElementStore(doc)
    const id = store.create(baseRect())
    swapStrokeAndFill(store, new Set([id]))
    const el = store.get(id)
    expect(el?.strokeColor).toBe('#a5d8ff')
    expect(el?.fillColor).toBe('#1e1e1e')
  })

  it('promotes fillStyle:none to solid when the swap puts a real colour into the fill slot', () => {
    const doc = new Y.Doc()
    const store = createElementStore(doc)
    const id = store.create(
      baseRect({
        strokeColor: '#ff0000',
        fillColor: 'transparent',
        fillStyle: 'none',
      }),
    )
    swapStrokeAndFill(store, new Set([id]))
    const el = store.get(id)
    // After swap: stroke='transparent', fill='#ff0000'. fillStyle
    // was 'none' before — promoted to 'solid' so the red actually
    // paints.
    expect(el?.fillColor).toBe('#ff0000')
    expect(el?.fillStyle).toBe('solid')
  })

  it('demotes fillStyle to none when the swap puts transparent into the fill slot', () => {
    const doc = new Y.Doc()
    const store = createElementStore(doc)
    const id = store.create(
      baseRect({
        strokeColor: 'transparent',
        fillColor: '#a5d8ff',
        fillStyle: 'solid',
      }),
    )
    swapStrokeAndFill(store, new Set([id]))
    const el = store.get(id)
    // After swap: stroke='#a5d8ff', fill='transparent'. fillStyle
    // demoted to 'none' so the data model stays consistent.
    expect(el?.fillColor).toBe('transparent')
    expect(el?.fillStyle).toBe('none')
  })

  it('leaves fillStyle alone when it was solid AND remains solid', () => {
    const doc = new Y.Doc()
    const store = createElementStore(doc)
    const id = store.create(baseRect({ fillStyle: 'hatch' }))
    swapStrokeAndFill(store, new Set([id]))
    const el = store.get(id)
    // Pattern fills + opaque fill colour → leave fillStyle as-is.
    expect(el?.fillStyle).toBe('hatch')
  })

  it('handles a multi-element selection in one pass', () => {
    const doc = new Y.Doc()
    const store = createElementStore(doc)
    const a = store.create(
      baseRect({ strokeColor: '#ff0000', fillColor: '#00ff00' }),
    )
    const b = store.create(
      baseRect({ strokeColor: '#0000ff', fillColor: '#ffff00' }),
    )
    swapStrokeAndFill(store, new Set([a, b]))
    expect(store.get(a)?.strokeColor).toBe('#00ff00')
    expect(store.get(a)?.fillColor).toBe('#ff0000')
    expect(store.get(b)?.strokeColor).toBe('#ffff00')
    expect(store.get(b)?.fillColor).toBe('#0000ff')
  })

  it('is a no-op for an empty selection', () => {
    const doc = new Y.Doc()
    const store = createElementStore(doc)
    const id = store.create(baseRect())
    swapStrokeAndFill(store, new Set())
    const el = store.get(id)
    expect(el?.strokeColor).toBe('#1e1e1e')
    expect(el?.fillColor).toBe('#a5d8ff')
  })

  it('skips ids that no longer resolve in the store', () => {
    const doc = new Y.Doc()
    const store = createElementStore(doc)
    const id = store.create(baseRect())
    expect(() => swapStrokeAndFill(store, new Set([id, 'ghost']))).not.toThrow()
    expect(store.get(id)?.strokeColor).toBe('#a5d8ff')
  })

  it('round-trips — two swaps return the original colours', () => {
    const doc = new Y.Doc()
    const store = createElementStore(doc)
    const id = store.create(baseRect())
    swapStrokeAndFill(store, new Set([id]))
    swapStrokeAndFill(store, new Set([id]))
    const el = store.get(id)
    expect(el?.strokeColor).toBe('#1e1e1e')
    expect(el?.fillColor).toBe('#a5d8ff')
  })
})
