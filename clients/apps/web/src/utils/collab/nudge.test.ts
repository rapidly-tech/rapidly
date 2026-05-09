/**
 * Nudge — pinned behaviour:
 *
 * - Translates every selected unlocked element by (dx, dy).
 * - Locked elements are skipped.
 * - Empty selection / zero delta is a no-op.
 * - Bound arrow endpoints follow their target.
 * - All updates land in a single Yjs transaction (one undo step).
 * - ``deltaFromArrowKey`` maps the four arrow keys; null for others.
 * - Shift uses the large step.
 */

import { describe, expect, it } from 'vitest'
import * as Y from 'yjs'

import { createElementStore } from './element-store'
import {
  DEFAULT_NUDGE_LARGE_STEP,
  DEFAULT_NUDGE_STEP,
  deltaFromArrowKey,
  nudge,
} from './nudge'

describe('nudge', () => {
  it('translates a single element by the delta', () => {
    const store = createElementStore(new Y.Doc())
    const id = store.create({
      type: 'rect',
      x: 100,
      y: 50,
      width: 20,
      height: 20,
    })
    const moved = nudge(store, new Set([id]), 5, -3)
    expect(moved).toBe(1)
    expect(store.get(id)?.x).toBe(105)
    expect(store.get(id)?.y).toBe(47)
  })

  it('skips locked elements', () => {
    const store = createElementStore(new Y.Doc())
    const a = store.create({
      type: 'rect',
      x: 0,
      y: 0,
      width: 20,
      height: 20,
    })
    const b = store.create({
      type: 'rect',
      x: 100,
      y: 0,
      width: 20,
      height: 20,
      locked: true,
    })
    const moved = nudge(store, new Set([a, b]), 10, 10)
    expect(moved).toBe(1)
    expect(store.get(a)?.x).toBe(10)
    expect(store.get(b)?.x).toBe(100)
  })

  it('is a no-op on empty selection', () => {
    const store = createElementStore(new Y.Doc())
    expect(nudge(store, new Set(), 5, 5)).toBe(0)
  })

  it('is a no-op on zero delta', () => {
    const store = createElementStore(new Y.Doc())
    const id = store.create({
      type: 'rect',
      x: 10,
      y: 10,
      width: 20,
      height: 20,
    })
    expect(nudge(store, new Set([id]), 0, 0)).toBe(0)
    expect(store.get(id)?.x).toBe(10)
  })

  it('runs the whole nudge in a single Yjs transaction', () => {
    const doc = new Y.Doc()
    const store = createElementStore(doc)
    const a = store.create({
      type: 'rect',
      x: 0,
      y: 0,
      width: 20,
      height: 20,
    })
    const b = store.create({
      type: 'rect',
      x: 100,
      y: 0,
      width: 20,
      height: 20,
    })
    let txCount = 0
    doc.on('afterTransaction', () => {
      txCount++
    })
    nudge(store, new Set([a, b]), 5, 5)
    expect(txCount).toBe(1)
  })
})

describe('deltaFromArrowKey', () => {
  it('maps the four arrow keys', () => {
    expect(deltaFromArrowKey('ArrowLeft', false)).toEqual({
      dx: -DEFAULT_NUDGE_STEP,
      dy: 0,
    })
    expect(deltaFromArrowKey('ArrowRight', false)).toEqual({
      dx: DEFAULT_NUDGE_STEP,
      dy: 0,
    })
    expect(deltaFromArrowKey('ArrowUp', false)).toEqual({
      dx: 0,
      dy: -DEFAULT_NUDGE_STEP,
    })
    expect(deltaFromArrowKey('ArrowDown', false)).toEqual({
      dx: 0,
      dy: DEFAULT_NUDGE_STEP,
    })
  })

  it('uses the large step when shift is held', () => {
    expect(deltaFromArrowKey('ArrowRight', true)).toEqual({
      dx: DEFAULT_NUDGE_LARGE_STEP,
      dy: 0,
    })
  })

  it('returns null for non-arrow keys', () => {
    expect(deltaFromArrowKey('Tab', false)).toBeNull()
    expect(deltaFromArrowKey(' ', false)).toBeNull()
    expect(deltaFromArrowKey('PageDown', false)).toBeNull()
  })

  it('respects custom steps', () => {
    expect(deltaFromArrowKey('ArrowRight', false, 5, 50)).toEqual({
      dx: 5,
      dy: 0,
    })
    expect(deltaFromArrowKey('ArrowRight', true, 5, 50)).toEqual({
      dx: 50,
      dy: 0,
    })
  })
})
