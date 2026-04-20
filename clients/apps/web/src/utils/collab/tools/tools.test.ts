/**
 * Tool-dispatch unit tests.
 *
 * Tools are pure event-handlers on top of ``ToolCtx``, so we feed them
 * a stub ctx backed by a real ``ElementStore`` (to exercise Yjs
 * transactions + origin tagging) and assert on the resulting element
 * state. No canvas, no React.
 */

import { describe, expect, it } from 'vitest'
import * as Y from 'yjs'

import { createElementStore, type ElementStore } from '../element-store'
import { makeViewport, type Viewport } from '../viewport'
import { ellipseTool, handTool, rectTool, toolFor } from './index'
import type { Tool, ToolCtx } from './types'

function stubCtx(store: ElementStore): ToolCtx {
  const viewport: Viewport = makeViewport()
  // Minimal renderer stand-in — the tools only need ``getViewport`` +
  // ``setViewport`` for the hand tool. Everything else goes through
  // the store.
  const renderer = {
    getViewport: () => viewport,
    setViewport: () => {},
  } as unknown as ToolCtx['renderer']
  return {
    store,
    renderer,
    viewport,
    screenToWorld: (x, y) => ({ x, y }),
    invalidate: () => {},
  }
}

/** Build a synthetic PointerEvent. jsdom supports real PointerEvent
 *  in recent versions; fall back to a duck-typed object for older. */
function makeEvent(
  clientX: number,
  clientY: number,
  opts: { shift?: boolean; alt?: boolean } = {},
): PointerEvent {
  return {
    clientX,
    clientY,
    shiftKey: !!opts.shift,
    altKey: !!opts.alt,
    target: {
      getBoundingClientRect: () => ({ left: 0, top: 0 }),
    },
  } as unknown as PointerEvent
}

describe('toolFor registry', () => {
  it('resolves implemented tools', () => {
    expect(toolFor('hand')).toBe(handTool)
    expect(toolFor('rect')).toBe(rectTool)
    expect(toolFor('ellipse')).toBe(ellipseTool)
  })

  it('returns null for unimplemented tools', () => {
    expect(toolFor('select')).toBeNull()
    expect(toolFor('freedraw')).toBeNull()
  })
})

describe('rectTool', () => {
  it('creates, resizes, and commits a rect via a full gesture', () => {
    const doc = new Y.Doc()
    const store = createElementStore(doc)
    const ctx = stubCtx(store)

    rectTool.onPointerDown(ctx, makeEvent(10, 20))
    expect(store.size).toBe(1)
    const id = store.list()[0].id
    expect(store.get(id)?.width).toBe(0)

    rectTool.onPointerMove(ctx, makeEvent(110, 70))
    const midway = store.get(id)
    expect(midway?.x).toBe(10)
    expect(midway?.y).toBe(20)
    expect(midway?.width).toBe(100)
    expect(midway?.height).toBe(50)

    rectTool.onPointerUp(ctx, makeEvent(110, 70))
    expect(store.size).toBe(1)
  })

  it('shift constrains to a square', () => {
    const doc = new Y.Doc()
    const store = createElementStore(doc)
    const ctx = stubCtx(store)
    rectTool.onPointerDown(ctx, makeEvent(0, 0))
    rectTool.onPointerMove(ctx, makeEvent(100, 40, { shift: true }))
    const el = store.list()[0]
    expect(el.width).toBe(100)
    expect(el.height).toBe(100)
    rectTool.onPointerUp(ctx, makeEvent(100, 40))
  })

  it('alt draws from the centre outward', () => {
    const doc = new Y.Doc()
    const store = createElementStore(doc)
    const ctx = stubCtx(store)
    rectTool.onPointerDown(ctx, makeEvent(50, 50))
    rectTool.onPointerMove(ctx, makeEvent(80, 70, { alt: true }))
    const el = store.list()[0]
    // Anchor was (50,50); drag to (80,70) with alt → centred on
    // anchor, 60×40 rect stretching from (20,30) to (80,70).
    expect(el.x).toBe(20)
    expect(el.y).toBe(30)
    expect(el.width).toBe(60)
    expect(el.height).toBe(40)
    rectTool.onPointerUp(ctx, makeEvent(80, 70))
  })

  it('drops a sub-pixel rect on pointer-up (accidental tap)', () => {
    const doc = new Y.Doc()
    const store = createElementStore(doc)
    const ctx = stubCtx(store)
    rectTool.onPointerDown(ctx, makeEvent(0, 0))
    rectTool.onPointerMove(ctx, makeEvent(2, 2))
    rectTool.onPointerUp(ctx, makeEvent(2, 2))
    expect(store.size).toBe(0)
  })

  it('onCancel discards the in-progress rect', () => {
    const doc = new Y.Doc()
    const store = createElementStore(doc)
    const ctx = stubCtx(store)
    rectTool.onPointerDown(ctx, makeEvent(0, 0))
    rectTool.onPointerMove(ctx, makeEvent(50, 50))
    rectTool.onCancel?.(ctx)
    expect(store.size).toBe(0)
  })

  it('drag up-left normalises to a positive rect', () => {
    const doc = new Y.Doc()
    const store = createElementStore(doc)
    const ctx = stubCtx(store)
    rectTool.onPointerDown(ctx, makeEvent(100, 100))
    rectTool.onPointerMove(ctx, makeEvent(40, 60))
    const el = store.list()[0]
    expect(el.x).toBe(40)
    expect(el.y).toBe(60)
    expect(el.width).toBe(60)
    expect(el.height).toBe(40)
    rectTool.onPointerUp(ctx, makeEvent(40, 60))
  })
})

describe('ellipseTool', () => {
  it('creates and resizes an ellipse', () => {
    const doc = new Y.Doc()
    const store = createElementStore(doc)
    const ctx = stubCtx(store)
    ellipseTool.onPointerDown(ctx, makeEvent(10, 20))
    ellipseTool.onPointerMove(ctx, makeEvent(110, 70))
    ellipseTool.onPointerUp(ctx, makeEvent(110, 70))
    const el = store.list()[0]
    expect(el.type).toBe('ellipse')
    expect(el.width).toBe(100)
    expect(el.height).toBe(50)
  })

  it('drops a sub-pixel ellipse', () => {
    const doc = new Y.Doc()
    const store = createElementStore(doc)
    const ctx = stubCtx(store)
    ellipseTool.onPointerDown(ctx, makeEvent(0, 0))
    ellipseTool.onPointerMove(ctx, makeEvent(1, 1))
    ellipseTool.onPointerUp(ctx, makeEvent(1, 1))
    expect(store.size).toBe(0)
  })
})

describe('handTool', () => {
  it('tool is a real Tool with a cursor + handlers', () => {
    const t: Tool = handTool
    expect(t.id).toBe('hand')
    expect(typeof t.cursor).toBe('string')
    expect(typeof t.onPointerDown).toBe('function')
    expect(typeof t.onPointerUp).toBe('function')
  })
})
