import { describe, expect, it } from 'vitest'
import * as Y from 'yjs'

import { createElementStore } from './element-store'
import {
  applyToSelection,
  CONVERTIBLE_TYPES,
  FILL_STYLES,
  FONT_FAMILIES,
  FONT_SIZES,
  ROUNDNESS_PRESETS,
  sharedField,
  STROKE_STYLES,
  TEXT_ALIGNMENTS,
} from './properties'

describe('sharedField', () => {
  it('returns null for an empty selection', () => {
    const doc = new Y.Doc()
    const store = createElementStore(doc)
    expect(sharedField(store, new Set(), 'strokeColor')).toBeNull()
  })

  it('returns the shared value when all selected match', () => {
    const doc = new Y.Doc()
    const store = createElementStore(doc)
    const a = store.create({
      type: 'rect',
      x: 0,
      y: 0,
      width: 10,
      height: 10,
      roundness: 0,
      strokeColor: '#ff0000',
    })
    const b = store.create({
      type: 'rect',
      x: 0,
      y: 0,
      width: 10,
      height: 10,
      roundness: 0,
      strokeColor: '#ff0000',
    })
    expect(sharedField(store, new Set([a, b]), 'strokeColor')).toBe('#ff0000')
  })

  it("returns 'mixed' when values differ", () => {
    const doc = new Y.Doc()
    const store = createElementStore(doc)
    const a = store.create({
      type: 'rect',
      x: 0,
      y: 0,
      width: 10,
      height: 10,
      roundness: 0,
      strokeColor: '#ff0000',
    })
    const b = store.create({
      type: 'rect',
      x: 0,
      y: 0,
      width: 10,
      height: 10,
      roundness: 0,
      strokeColor: '#00ff00',
    })
    expect(sharedField(store, new Set([a, b]), 'strokeColor')).toBe('mixed')
  })

  it('ignores ids that are not in the store', () => {
    const doc = new Y.Doc()
    const store = createElementStore(doc)
    const a = store.create({
      type: 'rect',
      x: 0,
      y: 0,
      width: 10,
      height: 10,
      roundness: 0,
      strokeColor: '#fafafa',
    })
    expect(sharedField(store, new Set([a, 'ghost']), 'strokeColor')).toBe(
      '#fafafa',
    )
  })
})

describe('applyToSelection', () => {
  it('emits a single Yjs update per call regardless of selection size', () => {
    const doc = new Y.Doc()
    const store = createElementStore(doc)
    const a = store.create({
      type: 'rect',
      x: 0,
      y: 0,
      width: 10,
      height: 10,
      roundness: 0,
    })
    const b = store.create({
      type: 'rect',
      x: 0,
      y: 0,
      width: 10,
      height: 10,
      roundness: 0,
    })
    const c = store.create({
      type: 'rect',
      x: 0,
      y: 0,
      width: 10,
      height: 10,
      roundness: 0,
    })
    let updates = 0
    doc.on('update', () => {
      updates++
    })
    applyToSelection(store, new Set([a, b, c]), { opacity: 50 })
    expect(updates).toBe(1)
    expect(store.get(a)?.opacity).toBe(50)
    expect(store.get(b)?.opacity).toBe(50)
    expect(store.get(c)?.opacity).toBe(50)
  })

  it('is a no-op when selection is empty', () => {
    const doc = new Y.Doc()
    const store = createElementStore(doc)
    let updates = 0
    doc.on('update', () => {
      updates++
    })
    applyToSelection(store, new Set(), { opacity: 50 })
    expect(updates).toBe(0)
  })
})

describe('property-picker constants', () => {
  it('CONVERTIBLE_TYPES exposes the three closed shape types', () => {
    expect(CONVERTIBLE_TYPES.map((t) => t.id).sort()).toEqual([
      'diamond',
      'ellipse',
      'rect',
    ])
  })

  it('FILL_STYLES covers solid + the three patterned variants', () => {
    expect(FILL_STYLES.map((s) => s.id).sort()).toEqual([
      'cross-hatch',
      'dots',
      'hatch',
      'solid',
    ])
  })

  it('STROKE_STYLES covers Excalidraw\'s three line treatments', () => {
    expect([...STROKE_STYLES].sort()).toEqual(['dashed', 'dotted', 'solid'])
  })

  it('FONT_FAMILIES, FONT_SIZES, TEXT_ALIGNMENTS are non-empty', () => {
    expect(FONT_FAMILIES.length).toBeGreaterThan(0)
    expect(FONT_SIZES.length).toBeGreaterThan(0)
    expect(TEXT_ALIGNMENTS.length).toBeGreaterThan(0)
  })

  it('ROUNDNESS_PRESETS has sharp + round entries', () => {
    expect(ROUNDNESS_PRESETS.map((p) => p.id).sort()).toEqual([
      'round',
      'sharp',
    ])
  })
})
