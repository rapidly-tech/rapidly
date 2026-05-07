import { afterEach, describe, expect, it } from 'vitest'
import * as Y from 'yjs'

import { createElementStore } from './element-store'
import type { CollabElement } from './elements'
import {
  clearStyleBuffer,
  copyStyle,
  hasStyle,
  pasteStyle,
  STYLE_FIELDS,
} from './style-clipboard'

const baseRect = {
  type: 'rect' as const,
  x: 0,
  y: 0,
  width: 100,
  height: 60,
  roundness: 0,
  strokeColor: '#ff0000',
  fillColor: '#a5d8ff',
  fillStyle: 'solid' as const,
  strokeWidth: 2,
  strokeStyle: 'solid' as const,
  roughness: 0 as const,
  opacity: 80,
}

const baseText = {
  type: 'text' as const,
  x: 0,
  y: 0,
  width: 100,
  height: 20,
  text: 'hi',
  fontFamily: 'sans' as const,
  fontSize: 16,
  textAlign: 'left' as const,
  fontWeight: 'bold' as const,
  fontStyle: 'italic' as const,
  lineHeight: 1.4,
  letterSpacing: 0.05,
  strokeColor: '#1e1e1e',
}

afterEach(() => {
  clearStyleBuffer()
})

describe('copyStyle', () => {
  it('captures every supported style field that the element carries', () => {
    const doc = new Y.Doc()
    const store = createElementStore(doc)
    const id = store.create(baseRect)
    const style = copyStyle(store.get(id) as CollabElement)
    expect(style.strokeColor).toBe('#ff0000')
    expect(style.fillColor).toBe('#a5d8ff')
    expect(style.fillStyle).toBe('solid')
    expect(style.strokeWidth).toBe(2)
    expect(style.opacity).toBe(80)
    expect(style.roundness).toBe(0)
  })

  it('omits fields the element does not carry', () => {
    const doc = new Y.Doc()
    const store = createElementStore(doc)
    const id = store.create(baseRect)
    const style = copyStyle(store.get(id) as CollabElement)
    // ``rect`` doesn't have a font, so the style record shouldn't
    // either — pasting onto a text mustn't blank its typography.
    expect(style.fontFamily).toBeUndefined()
    expect(style.fontSize).toBeUndefined()
  })

  it('captures typography fields from a text element', () => {
    const doc = new Y.Doc()
    const store = createElementStore(doc)
    const id = store.create(baseText)
    const style = copyStyle(store.get(id) as CollabElement)
    expect(style.fontFamily).toBe('sans')
    expect(style.fontSize).toBe(16)
    expect(style.textAlign).toBe('left')
    expect(style.fontWeight).toBe('bold')
    expect(style.fontStyle).toBe('italic')
    expect(style.lineHeight).toBe(1.4)
    expect(style.letterSpacing).toBe(0.05)
  })
})

describe('pasteStyle', () => {
  it('applies every captured field to every target', () => {
    const doc = new Y.Doc()
    const store = createElementStore(doc)
    const source = store.create(baseRect)
    const a = store.create({ ...baseRect, strokeColor: '#000000' })
    const b = store.create({ ...baseRect, strokeColor: '#000000' })
    copyStyle(store.get(source) as CollabElement)
    const ok = pasteStyle(store, new Set([a, b]))
    expect(ok).toBe(true)
    expect(store.get(a)?.strokeColor).toBe('#ff0000')
    expect(store.get(b)?.strokeColor).toBe('#ff0000')
  })

  it('returns false when nothing has been copied yet', () => {
    const doc = new Y.Doc()
    const store = createElementStore(doc)
    const a = store.create(baseRect)
    expect(pasteStyle(store, new Set([a]))).toBe(false)
  })

  it('returns false when the target selection is empty', () => {
    const doc = new Y.Doc()
    const store = createElementStore(doc)
    const source = store.create(baseRect)
    copyStyle(store.get(source) as CollabElement)
    expect(pasteStyle(store, new Set())).toBe(false)
  })

  it('accepts an explicit style record (test seam — DI for the keybinding)', () => {
    const doc = new Y.Doc()
    const store = createElementStore(doc)
    const a = store.create({ ...baseRect, strokeColor: '#000000' })
    const ok = pasteStyle(store, new Set([a]), {
      strokeColor: '#aabbcc',
      opacity: 50,
    })
    expect(ok).toBe(true)
    expect(store.get(a)?.strokeColor).toBe('#aabbcc')
    expect(store.get(a)?.opacity).toBe(50)
  })

  it("doesn't overwrite typography on a non-text target when the source is a rect", () => {
    const doc = new Y.Doc()
    const store = createElementStore(doc)
    const source = store.create(baseRect)
    const text = store.create(baseText)
    copyStyle(store.get(source) as CollabElement)
    pasteStyle(store, new Set([text]))
    // The text's font should be untouched — copyStyle didn't capture
    // typography from the rect, so paste has nothing to apply.
    const updated = store.get(text) as CollabElement
    expect((updated as { fontFamily?: string }).fontFamily).toBe('sans')
    expect((updated as { fontSize?: number }).fontSize).toBe(16)
  })
})

describe('hasStyle', () => {
  it('returns false initially', () => {
    expect(hasStyle()).toBe(false)
  })

  it('returns true after a copy', () => {
    const doc = new Y.Doc()
    const store = createElementStore(doc)
    const id = store.create(baseRect)
    copyStyle(store.get(id) as CollabElement)
    expect(hasStyle()).toBe(true)
  })

  it('clearStyleBuffer resets the predicate', () => {
    const doc = new Y.Doc()
    const store = createElementStore(doc)
    const id = store.create(baseRect)
    copyStyle(store.get(id) as CollabElement)
    clearStyleBuffer()
    expect(hasStyle()).toBe(false)
  })
})

describe('STYLE_FIELDS', () => {
  it('lists exactly the documented style fields (no accidental drift)', () => {
    expect([...STYLE_FIELDS].sort()).toEqual(
      [
        'fillColor',
        'fillStyle',
        'fontFamily',
        'fontSize',
        'fontStyle',
        'fontWeight',
        'letterSpacing',
        'lineHeight',
        'opacity',
        'roughness',
        'roundness',
        'strokeColor',
        'strokeStyle',
        'strokeWidth',
        'textAlign',
      ].sort(),
    )
  })
})
