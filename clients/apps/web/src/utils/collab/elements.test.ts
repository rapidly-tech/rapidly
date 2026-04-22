import { describe, expect, it } from 'vitest'

import {
  isArrow,
  isCollabElement,
  isDiamond,
  isEllipse,
  isEmbed,
  isFrame,
  isFreeDraw,
  isImage,
  isLine,
  isRect,
  isSticky,
  isText,
  paintOrder,
  type CollabElement,
} from './elements'

/** A minimal valid element — every required field on BaseElement with a
 *  legal value. Individual tests override specific fields to verify
 *  guard behaviour. */
function validBase(overrides: Partial<Record<string, unknown>> = {}) {
  return {
    id: 'el-1',
    type: 'rect',
    x: 0,
    y: 0,
    width: 100,
    height: 50,
    angle: 0,
    zIndex: 1,
    strokeWidth: 2,
    opacity: 100,
    seed: 42,
    version: 1,
    locked: false,
    groupIds: [] as string[],
    strokeColor: '#000',
    fillColor: 'transparent',
    fillStyle: 'none',
    strokeStyle: 'solid',
    roughness: 1,
    ...overrides,
  }
}

describe('isCollabElement', () => {
  it('accepts a minimal valid element', () => {
    expect(isCollabElement(validBase())).toBe(true)
  })

  it('rejects non-objects', () => {
    expect(isCollabElement(null)).toBe(false)
    expect(isCollabElement(undefined)).toBe(false)
    expect(isCollabElement(42)).toBe(false)
    expect(isCollabElement('element')).toBe(false)
    expect(isCollabElement(true)).toBe(false)
  })

  it('rejects an empty id', () => {
    expect(isCollabElement(validBase({ id: '' }))).toBe(false)
  })

  it('rejects a missing or non-string id', () => {
    expect(isCollabElement(validBase({ id: undefined }))).toBe(false)
    expect(isCollabElement(validBase({ id: 123 }))).toBe(false)
  })

  it('rejects unknown element types', () => {
    expect(isCollabElement(validBase({ type: 'widget' }))).toBe(false)
    expect(isCollabElement(validBase({ type: '' }))).toBe(false)
  })

  it('accepts every known element type', () => {
    const types = [
      'rect',
      'ellipse',
      'diamond',
      'arrow',
      'line',
      'freedraw',
      'text',
      'sticky',
      'image',
      'frame',
      'embed',
    ] as const
    for (const type of types) {
      expect(isCollabElement(validBase({ type }))).toBe(true)
    }
  })

  it('rejects when any required numeric field is missing', () => {
    for (const key of [
      'x',
      'y',
      'width',
      'height',
      'angle',
      'zIndex',
      'strokeWidth',
      'opacity',
      'seed',
      'version',
    ]) {
      expect(isCollabElement(validBase({ [key]: undefined }))).toBe(false)
    }
  })

  it('rejects NaN / Infinity in numeric fields', () => {
    expect(isCollabElement(validBase({ x: NaN }))).toBe(false)
    expect(isCollabElement(validBase({ y: Infinity }))).toBe(false)
    expect(isCollabElement(validBase({ width: -Infinity }))).toBe(false)
  })

  it('rejects a non-boolean locked', () => {
    expect(isCollabElement(validBase({ locked: 'true' }))).toBe(false)
    expect(isCollabElement(validBase({ locked: 1 }))).toBe(false)
    expect(isCollabElement(validBase({ locked: undefined }))).toBe(false)
  })

  it('rejects groupIds that is not an array', () => {
    expect(isCollabElement(validBase({ groupIds: 'g1' }))).toBe(false)
    expect(isCollabElement(validBase({ groupIds: undefined }))).toBe(false)
  })

  it('rejects groupIds containing non-strings', () => {
    expect(isCollabElement(validBase({ groupIds: ['g1', 42] }))).toBe(false)
    expect(isCollabElement(validBase({ groupIds: [null] }))).toBe(false)
  })

  it('accepts empty groupIds', () => {
    expect(isCollabElement(validBase({ groupIds: [] }))).toBe(true)
  })
})

describe('per-type guards', () => {
  it('each narrows only its matching type', () => {
    const rect = validBase({ type: 'rect' }) as unknown as CollabElement
    const ellipse = validBase({ type: 'ellipse' }) as unknown as CollabElement
    const diamond = validBase({ type: 'diamond' }) as unknown as CollabElement
    const arrow = validBase({
      type: 'arrow',
      points: [0, 0, 10, 10],
    }) as unknown as CollabElement
    const line = validBase({
      type: 'line',
      points: [0, 0, 10, 10],
    }) as unknown as CollabElement
    const freedraw = validBase({
      type: 'freedraw',
      points: [0, 0, 0.5],
      simulatePressure: false,
    }) as unknown as CollabElement
    const text = validBase({
      type: 'text',
      text: 'hi',
      fontSize: 20,
      fontFamily: 'handwritten',
      textAlign: 'left',
    }) as unknown as CollabElement
    const sticky = validBase({
      type: 'sticky',
      text: 'note',
    }) as unknown as CollabElement
    const image = validBase({
      type: 'image',
      thumbnail: 'data:image/png;base64,',
    }) as unknown as CollabElement
    const frame = validBase({
      type: 'frame',
      childIds: [],
    }) as unknown as CollabElement
    const embed = validBase({
      type: 'embed',
      url: 'https://example.com',
    }) as unknown as CollabElement

    expect(isRect(rect)).toBe(true)
    expect(isRect(ellipse)).toBe(false)

    expect(isEllipse(ellipse)).toBe(true)
    expect(isEllipse(rect)).toBe(false)

    expect(isDiamond(diamond)).toBe(true)
    expect(isArrow(arrow)).toBe(true)
    expect(isLine(line)).toBe(true)
    expect(isFreeDraw(freedraw)).toBe(true)
    expect(isText(text)).toBe(true)
    expect(isSticky(sticky)).toBe(true)
    expect(isImage(image)).toBe(true)
    expect(isFrame(frame)).toBe(true)
    expect(isEmbed(embed)).toBe(true)

    // Cross-check: every guard rejects a rect of the wrong type.
    expect(isEllipse(rect)).toBe(false)
    expect(isDiamond(rect)).toBe(false)
    expect(isArrow(rect)).toBe(false)
    expect(isLine(rect)).toBe(false)
    expect(isFreeDraw(rect)).toBe(false)
    expect(isText(rect)).toBe(false)
    expect(isSticky(rect)).toBe(false)
    expect(isImage(rect)).toBe(false)
    expect(isFrame(rect)).toBe(false)
    expect(isEmbed(rect)).toBe(false)
  })
})

describe('paintOrder', () => {
  function el(id: string, zIndex: number): CollabElement {
    return validBase({ id, zIndex }) as unknown as CollabElement
  }

  it('orders by zIndex ascending', () => {
    const a = el('a', 1)
    const b = el('b', 2)
    expect(paintOrder(a, b)).toBeLessThan(0)
    expect(paintOrder(b, a)).toBeGreaterThan(0)
  })

  it('falls back to lexicographic id when zIndex matches', () => {
    const alpha = el('aaa', 5)
    const beta = el('bbb', 5)
    expect(paintOrder(alpha, beta)).toBeLessThan(0)
    expect(paintOrder(beta, alpha)).toBeGreaterThan(0)
  })

  it('returns 0 for identical elements', () => {
    const a = el('same', 5)
    const b = el('same', 5)
    expect(paintOrder(a, b)).toBe(0)
  })

  it('sorts an array deterministically under concurrent reorder', () => {
    // Two peers both assign zIndex=7 — the tie-break by id should keep
    // every peer's sort stable.
    const items = [el('zeta', 7), el('alpha', 7), el('mike', 7)]
    const sorted = [...items].sort(paintOrder)
    expect(sorted.map((x) => x.id)).toEqual(['alpha', 'mike', 'zeta'])
  })

  it('respects zIndex first even when ids sort the other way', () => {
    const small = el('zzz', 1)
    const big = el('aaa', 9)
    const sorted = [small, big].sort(paintOrder)
    expect(sorted.map((x) => x.id)).toEqual(['zzz', 'aaa'])
  })
})
