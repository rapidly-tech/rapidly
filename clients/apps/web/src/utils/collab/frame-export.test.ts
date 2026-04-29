/**
 * Frame-level export — pinned behaviour:
 *
 * - ``elementsForFrame`` returns the frame + every child id.
 * - Children are returned in canonical paint order (not childIds[]
 *   order), so z-stack is preserved on export.
 * - Unknown frame id → empty list.
 * - A frame whose childIds reference deleted elements is fine —
 *   we return only the survivors.
 * - ``isFrameId`` distinguishes frame ids from other element ids.
 */

import { describe, expect, it } from 'vitest'

import type { CollabElement } from './elements'
import { elementsForFrame, isFrameId } from './frame-export'

function frame(id: string, childIds: string[], zIndex = 0): CollabElement {
  return {
    id,
    type: 'frame',
    name: 'Frame',
    childIds,
    x: 0,
    y: 0,
    width: 100,
    height: 100,
    angle: 0,
    zIndex,
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
  } as CollabElement
}

function rect(id: string, zIndex = 0): CollabElement {
  return {
    id,
    type: 'rect',
    x: 0,
    y: 0,
    width: 10,
    height: 10,
    angle: 0,
    zIndex,
    groupIds: [],
    strokeColor: '#000',
    fillColor: 'transparent',
    fillStyle: 'solid',
    strokeWidth: 1,
    strokeStyle: 'solid',
    roughness: 0,
    roundness: 0,
    opacity: 1,
    seed: 1,
    version: 1,
    locked: false,
  } as CollabElement
}

describe('elementsForFrame', () => {
  it('returns the frame plus its children', () => {
    const els = [rect('a'), rect('b'), frame('f', ['a', 'b'])]
    const subset = elementsForFrame(els, 'f')
    const ids = subset.map((e) => e.id).sort()
    expect(ids).toEqual(['a', 'b', 'f'])
  })

  it('preserves the input s paint order, not childIds order', () => {
    // childIds in 'b','a' order; input list in 'a','b','f'.
    const els = [rect('a'), rect('b'), frame('f', ['b', 'a'])]
    const subset = elementsForFrame(els, 'f')
    expect(subset.map((e) => e.id)).toEqual(['a', 'b', 'f'])
  })

  it('skips children that no longer exist', () => {
    // Stale childIds (a peer deleted an element); we just survive.
    const els = [rect('a'), frame('f', ['a', 'ghost'])]
    expect(
      elementsForFrame(els, 'f')
        .map((e) => e.id)
        .sort(),
    ).toEqual(['a', 'f'])
  })

  it('returns empty for unknown ids', () => {
    expect(elementsForFrame([], 'no-such')).toEqual([])
  })

  it('returns empty for a non-frame id', () => {
    expect(elementsForFrame([rect('a')], 'a')).toEqual([])
  })
})

describe('isFrameId', () => {
  it('returns true for a frame id', () => {
    expect(isFrameId([frame('f', [])], 'f')).toBe(true)
  })

  it('returns false for a rect id', () => {
    expect(isFrameId([rect('a')], 'a')).toBe(false)
  })

  it('returns false for an unknown id', () => {
    expect(isFrameId([], 'no-such')).toBe(false)
  })
})
