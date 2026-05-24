import { describe, expect, it } from 'vitest'
import * as Y from 'yjs'

import { createElementStore } from './element-store'
import type { CollabElement } from './elements'
import { applyReplacements, previewReplacements } from './replace-text'

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

const text = (id: string, body: string, name?: string): CollabElement =>
  ({
    type: 'text',
    id,
    x: 0,
    y: 0,
    width: 100,
    height: 20,
    text: body,
    fontFamily: 'sans',
    fontSize: 16,
    textAlign: 'left',
    name,
    ...baseFields,
  }) as CollabElement

const sticky = (id: string, body: string): CollabElement =>
  ({
    type: 'sticky',
    id,
    x: 0,
    y: 0,
    width: 100,
    height: 60,
    text: body,
    fontFamily: 'sans',
    fontSize: 14,
    textAlign: 'left',
    ...baseFields,
  }) as CollabElement

const frame = (id: string, name: string): CollabElement =>
  ({
    type: 'frame',
    id,
    x: 0,
    y: 0,
    width: 200,
    height: 200,
    name,
    childIds: [] as string[],
    ...baseFields,
  }) as CollabElement

const embed = (id: string, url: string): CollabElement =>
  ({
    type: 'embed',
    id,
    x: 0,
    y: 0,
    width: 320,
    height: 240,
    url,
    sandbox: '',
    ...baseFields,
  }) as CollabElement

const rect = (id: string, name?: string): CollabElement =>
  ({
    type: 'rect',
    id,
    x: 0,
    y: 0,
    width: 10,
    height: 10,
    roundness: 0,
    name,
    ...baseFields,
  }) as CollabElement

describe('previewReplacements', () => {
  it('returns no previews for an empty query', () => {
    expect(previewReplacements([text('a', 'Hello')], '', 'World')).toEqual([])
    expect(previewReplacements([text('a', 'Hello')], '   ', 'World')).toEqual(
      [],
    )
  })

  it('returns no previews when nothing matches', () => {
    expect(previewReplacements([text('a', 'Hello')], 'mango', 'X')).toEqual([])
  })

  it('finds + replaces a single text body', () => {
    const previews = previewReplacements(
      [text('a', 'Apple pie')],
      'apple',
      'Mango',
    )
    expect(previews).toEqual([
      {
        elementId: 'a',
        field: 'text',
        before: 'Apple pie',
        after: 'Mango pie',
      },
    ])
  })

  it('replaces every occurrence in a single string (global match)', () => {
    const previews = previewReplacements(
      [text('a', 'apple apple apple')],
      'apple',
      'X',
    )
    expect(previews[0].after).toBe('X X X')
  })

  it('match is case-insensitive but preserves the replacement casing', () => {
    const previews = previewReplacements(
      [text('a', 'Apple APPLE apple')],
      'apple',
      'mango',
    )
    expect(previews[0].after).toBe('mango mango mango')
  })

  it('rewrites sticky text', () => {
    const previews = previewReplacements(
      [sticky('s', 'TODO ship it')],
      'TODO',
      'DONE',
    )
    expect(previews[0].field).toBe('text')
    expect(previews[0].after).toBe('DONE ship it')
  })

  it('rewrites a frame name', () => {
    const previews = previewReplacements(
      [frame('f', 'Onboarding flow')],
      'flow',
      'screen',
    )
    expect(previews[0].field).toBe('name')
    expect(previews[0].after).toBe('Onboarding screen')
  })

  it('rewrites an embed URL', () => {
    const previews = previewReplacements(
      [embed('e', 'https://youtube.com/watch?v=abc')],
      'youtube',
      'vimeo',
    )
    expect(previews[0].field).toBe('url')
    expect(previews[0].after).toBe('https://vimeo.com/watch?v=abc')
  })

  it('rewrites the generic name field on a non-frame element', () => {
    const previews = previewReplacements(
      [rect('r', undefined as unknown as string), rect('r2', 'Login button')],
      'button',
      'box',
    )
    expect(previews).toHaveLength(1)
    expect(previews[0].elementId).toBe('r2')
    expect(previews[0].field).toBe('name')
    expect(previews[0].after).toBe('Login box')
  })

  it('treats the query literally — regex characters are escaped', () => {
    const previews = previewReplacements(
      [text('a', 'price: $1.50')],
      '$1.50',
      '$2.00',
    )
    expect(previews[0].after).toBe('price: $2.00')
  })

  it('emits one preview per touched field even when an element has multiple matches', () => {
    // Element has both a name and a body that match.
    const el = text('t', 'Apple body', 'Apple name')
    const previews = previewReplacements([el], 'Apple', 'Mango')
    expect(previews).toHaveLength(2)
    expect(previews.map((p) => p.field).sort()).toEqual(['name', 'text'])
  })

  it('skips fields whose value is unchanged', () => {
    // Empty text fields shouldn't leak into the preview.
    expect(previewReplacements([text('a', '')], 'apple', 'mango')).toEqual([])
  })
})

describe('applyReplacements', () => {
  it('writes every replacement back to the store', () => {
    const doc = new Y.Doc()
    const store = createElementStore(doc)
    const a = store.create({
      type: 'text',
      x: 0,
      y: 0,
      width: 100,
      height: 20,
      text: 'Apple pie',
      fontFamily: 'sans',
      fontSize: 16,
      textAlign: 'left',
    })
    const b = store.create({
      type: 'sticky',
      x: 0,
      y: 0,
      width: 100,
      height: 60,
      text: 'Apple sauce',
      fontFamily: 'sans',
      fontSize: 14,
      textAlign: 'left',
    })
    const elements = store.list() as unknown as CollabElement[]
    const count = applyReplacements(store, elements, 'apple', 'Mango')
    expect(count).toBe(2)
    expect((store.get(a) as { text: string }).text).toBe('Mango pie')
    expect((store.get(b) as { text: string }).text).toBe('Mango sauce')
  })

  it('returns 0 when nothing matches', () => {
    const doc = new Y.Doc()
    const store = createElementStore(doc)
    store.create({
      type: 'text',
      x: 0,
      y: 0,
      width: 100,
      height: 20,
      text: 'Hello',
      fontFamily: 'sans',
      fontSize: 16,
      textAlign: 'left',
    })
    const elements = store.list() as unknown as CollabElement[]
    expect(applyReplacements(store, elements, 'mango', 'X')).toBe(0)
  })

  it('collapses multiple field touches on the same element into one update', () => {
    const doc = new Y.Doc()
    const store = createElementStore(doc)
    const id = store.create({
      type: 'text',
      x: 0,
      y: 0,
      width: 100,
      height: 20,
      text: 'Apple body',
      name: 'Apple name',
      fontFamily: 'sans',
      fontSize: 16,
      textAlign: 'left',
    })
    const elements = store.list() as unknown as CollabElement[]
    applyReplacements(store, elements, 'Apple', 'Mango')
    const el = store.get(id) as { text: string; name: string }
    expect(el.text).toBe('Mango body')
    expect(el.name).toBe('Mango name')
  })
})
