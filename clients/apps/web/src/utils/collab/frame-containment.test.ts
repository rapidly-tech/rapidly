/**
 * Frame containment — pinned behaviour:
 *
 * - ``frameAtPoint`` returns the topmost frame whose bbox contains
 *   the point; null when none.
 * - ``updateFrameMembership`` adopts moved elements whose centre
 *   lands inside a frame; releases them when they leave.
 * - Frames themselves are not adopted (no nesting in this PR).
 * - Single Yjs transaction → single undo step.
 * - No childIds change → no version bump (no-op writes filtered out).
 */

import { describe, expect, it } from 'vitest'
import * as Y from 'yjs'

import { createElementStore } from './element-store'
import { frameAtPoint, updateFrameMembership } from './frame-containment'

describe('frameAtPoint', () => {
  const els = [
    { id: 'r', type: 'rect', x: 0, y: 0, width: 50, height: 50, zIndex: 0 },
    {
      id: 'f1',
      type: 'frame',
      x: 100,
      y: 100,
      width: 200,
      height: 200,
      zIndex: 1,
    },
    {
      id: 'f2',
      type: 'frame',
      x: 150,
      y: 150,
      width: 200,
      height: 200,
      zIndex: 2,
    },
  ]

  it('returns null when no frame contains the point', () => {
    expect(frameAtPoint(els, 5, 5)).toBeNull()
  })

  it('returns the topmost frame when stacked', () => {
    // Both f1 + f2 contain (175, 175); f2 has higher zIndex.
    const hit = frameAtPoint(els, 175, 175)
    expect(hit?.id).toBe('f2')
  })

  it('skips non-frame elements', () => {
    expect(frameAtPoint(els, 25, 25)).toBeNull()
  })
})

describe('updateFrameMembership', () => {
  it('adopts a moved element whose centre is inside a frame', () => {
    const doc = new Y.Doc()
    const store = createElementStore(doc)
    const fid = store.create({
      id: 'frame',
      type: 'frame',
      x: 100,
      y: 100,
      width: 200,
      height: 200,
      name: 'F',
      childIds: [],
    })
    const rid = store.create({
      id: 'rect',
      type: 'rect',
      x: 150,
      y: 150,
      width: 40,
      height: 40,
    })
    const changed = updateFrameMembership(store, new Set([rid]))
    expect(changed).toBe(1)
    const frame = store.get(fid) as { childIds: string[] }
    expect(frame.childIds).toEqual([rid])
  })

  it('releases a moved element when it leaves the frame', () => {
    const doc = new Y.Doc()
    const store = createElementStore(doc)
    const fid = store.create({
      id: 'frame',
      type: 'frame',
      x: 100,
      y: 100,
      width: 200,
      height: 200,
      name: 'F',
      childIds: ['rect'],
    })
    // Element sits OUTSIDE the frame now (centre at 25, 25).
    store.create({
      id: 'rect',
      type: 'rect',
      x: 0,
      y: 0,
      width: 50,
      height: 50,
    })
    updateFrameMembership(store, new Set(['rect']))
    const frame = store.get(fid) as { childIds: string[] }
    expect(frame.childIds).toEqual([])
  })

  it('hands off a moved element from one frame to another', () => {
    const doc = new Y.Doc()
    const store = createElementStore(doc)
    store.create({
      id: 'fa',
      type: 'frame',
      x: 0,
      y: 0,
      width: 100,
      height: 100,
      name: 'A',
      childIds: ['rect'],
    })
    store.create({
      id: 'fb',
      type: 'frame',
      x: 200,
      y: 0,
      width: 100,
      height: 100,
      name: 'B',
      childIds: [],
    })
    // Rect's centre at 250, 50 → inside frame B.
    store.create({
      id: 'rect',
      type: 'rect',
      x: 230,
      y: 30,
      width: 40,
      height: 40,
    })
    updateFrameMembership(store, new Set(['rect']))
    const a = store.get('fa') as { childIds: string[] }
    const b = store.get('fb') as { childIds: string[] }
    expect(a.childIds).toEqual([])
    expect(b.childIds).toEqual(['rect'])
  })

  it('skips moved frames (no nesting)', () => {
    const doc = new Y.Doc()
    const store = createElementStore(doc)
    store.create({
      id: 'outer',
      type: 'frame',
      x: 0,
      y: 0,
      width: 400,
      height: 400,
      name: 'Outer',
      childIds: [],
    })
    store.create({
      id: 'inner',
      type: 'frame',
      x: 100,
      y: 100,
      width: 100,
      height: 100,
      name: 'Inner',
      childIds: [],
    })
    updateFrameMembership(store, new Set(['inner']))
    const outer = store.get('outer') as { childIds: string[] }
    expect(outer.childIds).toEqual([])
  })

  it('no-ops when childIds would not change', () => {
    const doc = new Y.Doc()
    const store = createElementStore(doc)
    store.create({
      id: 'f',
      type: 'frame',
      x: 0,
      y: 0,
      width: 100,
      height: 100,
      name: 'F',
      childIds: ['r'],
    })
    store.create({
      id: 'r',
      type: 'rect',
      x: 25,
      y: 25,
      width: 25,
      height: 25,
    })
    expect(updateFrameMembership(store, new Set(['r']))).toBe(0)
  })

  it('runs the whole adoption in a single Yjs transaction', () => {
    const doc = new Y.Doc()
    const store = createElementStore(doc)
    store.create({
      id: 'fa',
      type: 'frame',
      x: 0,
      y: 0,
      width: 100,
      height: 100,
      name: 'A',
      childIds: [],
    })
    store.create({
      id: 'fb',
      type: 'frame',
      x: 200,
      y: 0,
      width: 100,
      height: 100,
      name: 'B',
      childIds: [],
    })
    store.create({
      id: 'r1',
      type: 'rect',
      x: 25,
      y: 25,
      width: 25,
      height: 25,
    })
    store.create({
      id: 'r2',
      type: 'rect',
      x: 225,
      y: 25,
      width: 25,
      height: 25,
    })
    let txCount = 0
    doc.on('afterTransaction', () => {
      txCount++
    })
    updateFrameMembership(store, new Set(['r1', 'r2']))
    expect(txCount).toBe(1)
  })
})
