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
import {
  arrowTool,
  diamondTool,
  ellipseTool,
  eraserTool,
  freedrawTool,
  handTool,
  lineTool,
  rectTool,
  stickyTool,
  textTool,
  toolFor,
} from './index'
import type { Tool, ToolCtx } from './types'

function stubCtx(store: ElementStore): ToolCtx {
  const viewport: Viewport = makeViewport()
  // Minimal renderer stand-in — the tools only need ``getViewport`` +
  // ``setViewport`` for the hand tool. Everything else goes through
  // the store.
  const renderer = {
    getViewport: () => viewport,
    setViewport: () => {},
    isGridEnabled: () => false,
    getGridSize: () => 20,
    isSnapToObjectsEnabled: () => false,
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
    expect(toolFor('diamond')).toBe(diamondTool)
    expect(toolFor('line')).toBe(lineTool)
  })

  it('resolves the eraser tool', () => {
    expect(toolFor('eraser')).toBe(eraserTool)
  })

  it('has arrow + freedraw + text + sticky wired up', () => {
    expect(toolFor('arrow')).toBe(arrowTool)
    expect(toolFor('freedraw')).toBe(freedrawTool)
    expect(toolFor('text')).toBe(textTool)
    expect(toolFor('sticky')).toBe(stickyTool)
  })
})

describe('stickyTool', () => {
  it('creates a fixed-size sticky at the cursor and requests edit', async () => {
    const doc = new Y.Doc()
    const store = createElementStore(doc)
    const ctx = stubCtx(store)
    const { _resetEditBroker, onEditRequest } = await import('../text-editing')
    _resetEditBroker()
    let requested: string | null = null
    onEditRequest((id) => {
      requested = id
    })

    stickyTool.onPointerDown(ctx, makeEvent(40, 50))
    const el = store.list()[0]
    expect(el.type).toBe('sticky')
    expect((el as { text: string }).text).toBe('')
    expect(el.x).toBe(40)
    expect(el.y).toBe(50)
    // Fixed-size — 160×160.
    expect(el.width).toBe(160)
    expect(el.height).toBe(160)
    expect(requested).toBe(el.id)
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

  it('snaps to the grid when renderer.isGridEnabled() is true', () => {
    const doc = new Y.Doc()
    const store = createElementStore(doc)
    const ctx = stubCtx(store)
    // Override grid to enabled, gridSize 20.
    ;(ctx.renderer as { isGridEnabled: () => boolean }).isGridEnabled = () =>
      true
    // Pointer at (11, 9) → snaps to (20, 0). Drag to (61, 41) → (60, 40).
    rectTool.onPointerDown(ctx, makeEvent(11, 9))
    rectTool.onPointerMove(ctx, makeEvent(61, 41))
    const el = store.list()[0]
    expect(el.x).toBe(20)
    expect(el.y).toBe(0)
    expect(el.width).toBe(40)
    expect(el.height).toBe(40)
    rectTool.onPointerUp(ctx, makeEvent(61, 41))
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

describe('diamondTool', () => {
  it('creates a diamond on drag', () => {
    const doc = new Y.Doc()
    const store = createElementStore(doc)
    const ctx = stubCtx(store)
    diamondTool.onPointerDown(ctx, makeEvent(0, 0))
    diamondTool.onPointerMove(ctx, makeEvent(120, 80))
    diamondTool.onPointerUp(ctx, makeEvent(120, 80))
    const el = store.list()[0]
    expect(el.type).toBe('diamond')
    expect(el.width).toBe(120)
    expect(el.height).toBe(80)
  })

  it('drops a sub-pixel diamond', () => {
    const doc = new Y.Doc()
    const store = createElementStore(doc)
    const ctx = stubCtx(store)
    diamondTool.onPointerDown(ctx, makeEvent(0, 0))
    diamondTool.onPointerMove(ctx, makeEvent(1, 1))
    diamondTool.onPointerUp(ctx, makeEvent(1, 1))
    expect(store.size).toBe(0)
  })
})

describe('lineTool', () => {
  it('creates a line with world-local points and AABB', () => {
    const doc = new Y.Doc()
    const store = createElementStore(doc)
    const ctx = stubCtx(store)
    lineTool.onPointerDown(ctx, makeEvent(10, 20))
    lineTool.onPointerMove(ctx, makeEvent(110, 70))
    lineTool.onPointerUp(ctx, makeEvent(110, 70))
    const el = store.list()[0]
    expect(el.type).toBe('line')
    expect(el.x).toBe(10)
    expect(el.y).toBe(20)
    expect(el.width).toBe(100)
    expect(el.height).toBe(50)
    expect((el as { points: number[] }).points).toEqual([0, 0, 100, 50])
  })

  it('shift snaps to 45°', () => {
    const doc = new Y.Doc()
    const store = createElementStore(doc)
    const ctx = stubCtx(store)
    // Drag something close to horizontal with shift — should snap to 0°.
    lineTool.onPointerDown(ctx, makeEvent(0, 0))
    lineTool.onPointerMove(ctx, makeEvent(100, 5, { shift: true }))
    const pts = (store.list()[0] as { points: number[] }).points
    // Snapped to 0° → second point's y should be at or extremely close to 0.
    expect(Math.abs(pts[3])).toBeLessThan(0.001)
    lineTool.onPointerUp(ctx, makeEvent(100, 5))
  })

  it('drops a line below the min-length threshold', () => {
    const doc = new Y.Doc()
    const store = createElementStore(doc)
    const ctx = stubCtx(store)
    lineTool.onPointerDown(ctx, makeEvent(0, 0))
    lineTool.onPointerMove(ctx, makeEvent(2, 2))
    lineTool.onPointerUp(ctx, makeEvent(2, 2))
    expect(store.size).toBe(0)
  })

  it('handles dragging up-left by producing positive AABB', () => {
    const doc = new Y.Doc()
    const store = createElementStore(doc)
    const ctx = stubCtx(store)
    lineTool.onPointerDown(ctx, makeEvent(100, 100))
    lineTool.onPointerMove(ctx, makeEvent(50, 30))
    const el = store.list()[0]
    expect(el.x).toBe(50)
    expect(el.y).toBe(30)
    expect(el.width).toBe(50)
    expect(el.height).toBe(70)
    lineTool.onPointerUp(ctx, makeEvent(50, 30))
  })

  it('snaps the second endpoint to a sibling element when snap-to-objects is on', () => {
    const doc = new Y.Doc()
    const store = createElementStore(doc)
    // Sibling rect's left edge sits at x=100. Drawing a line whose
    // second endpoint lands at x=99 should snap to 100.
    store.create({
      type: 'rect',
      x: 100,
      y: 1000, // far on y so y-axis can't snap
      width: 50,
      height: 50,
      roundness: 0,
    })
    const ctx = stubCtx(store)
    ;(
      ctx.renderer as { isSnapToObjectsEnabled: () => boolean }
    ).isSnapToObjectsEnabled = () => true

    lineTool.onPointerDown(ctx, makeEvent(0, 0))
    lineTool.onPointerMove(ctx, makeEvent(99, 0))
    const line = store.list().find((el) => el.type === 'line') as {
      points: number[]
    }
    // line.points[2] is the second endpoint x (element-local). With
    // anchor at 0, snapped endpoint at 100 → points[2] = 100.
    expect(line.points[2]).toBe(100)
    lineTool.onPointerUp(ctx, makeEvent(99, 0))
  })
})

describe('arrowTool', () => {
  it('creates an arrow with a default end triangle head', () => {
    const doc = new Y.Doc()
    const store = createElementStore(doc)
    const ctx = stubCtx(store)
    arrowTool.onPointerDown(ctx, makeEvent(10, 20))
    arrowTool.onPointerMove(ctx, makeEvent(110, 70))
    arrowTool.onPointerUp(ctx, makeEvent(110, 70))
    const el = store.list()[0] as {
      type: string
      points: number[]
      startArrowhead: string | null
      endArrowhead: string | null
    }
    expect(el.type).toBe('arrow')
    expect(el.points).toEqual([0, 0, 100, 50])
    expect(el.startArrowhead).toBeNull()
    expect(el.endArrowhead).toBe('triangle')
  })

  it('drops an arrow below the min-length threshold', () => {
    const doc = new Y.Doc()
    const store = createElementStore(doc)
    const ctx = stubCtx(store)
    arrowTool.onPointerDown(ctx, makeEvent(0, 0))
    arrowTool.onPointerMove(ctx, makeEvent(2, 2))
    arrowTool.onPointerUp(ctx, makeEvent(2, 2))
    expect(store.size).toBe(0)
  })
})

describe('freedrawTool', () => {
  function freedrawEvent(
    x: number,
    y: number,
    pressure = 0.5,
    pointerType: 'pen' | 'mouse' | 'touch' = 'pen',
  ): PointerEvent {
    return {
      clientX: x,
      clientY: y,
      shiftKey: false,
      altKey: false,
      pressure,
      pointerType,
      target: {
        getBoundingClientRect: () => ({ left: 0, top: 0 }),
      },
    } as unknown as PointerEvent
  }

  it('creates a freedraw element and appends (x, y, p) per sample', () => {
    const doc = new Y.Doc()
    const store = createElementStore(doc)
    const ctx = stubCtx(store)
    freedrawTool.onPointerDown(ctx, freedrawEvent(10, 10, 0.7))
    freedrawTool.onPointerMove(ctx, freedrawEvent(30, 20, 0.8))
    freedrawTool.onPointerMove(ctx, freedrawEvent(50, 30, 0.9))
    freedrawTool.onPointerUp(ctx, freedrawEvent(50, 30))
    const el = store.list()[0] as {
      type: string
      points: number[]
      width: number
      height: number
      simulatePressure: boolean
    }
    expect(el.type).toBe('freedraw')
    // 3 samples × 3 values per sample.
    expect(el.points.length).toBe(9)
    expect(el.width).toBe(40)
    expect(el.height).toBe(20)
    // Real pressure was provided → simulatePressure is false.
    expect(el.simulatePressure).toBe(false)
  })

  it('sets simulatePressure when the device reports no pressure', () => {
    const doc = new Y.Doc()
    const store = createElementStore(doc)
    const ctx = stubCtx(store)
    // Mouse pointer → treated as no reported pressure regardless of
    // the numeric value, so the tool simulates from velocity.
    freedrawTool.onPointerDown(ctx, freedrawEvent(0, 0, 0, 'mouse'))
    freedrawTool.onPointerMove(ctx, freedrawEvent(10, 10, 0, 'mouse'))
    freedrawTool.onPointerUp(ctx, freedrawEvent(10, 10, 0, 'mouse'))
    const el = store.list()[0] as { simulatePressure: boolean }
    expect(el.simulatePressure).toBe(true)
  })

  it('discards a single-sample stroke (accidental tap)', () => {
    const doc = new Y.Doc()
    const store = createElementStore(doc)
    const ctx = stubCtx(store)
    freedrawTool.onPointerDown(ctx, freedrawEvent(0, 0))
    // No moves — just tap and release.
    freedrawTool.onPointerUp(ctx, freedrawEvent(0, 0))
    expect(store.size).toBe(0)
  })

  it('ignores sub-pixel samples (under MIN_POINTER_DELTA)', () => {
    const doc = new Y.Doc()
    const store = createElementStore(doc)
    const ctx = stubCtx(store)
    freedrawTool.onPointerDown(ctx, freedrawEvent(0, 0))
    // Move by 0.1 — below the threshold.
    freedrawTool.onPointerMove(ctx, freedrawEvent(0.1, 0))
    freedrawTool.onPointerUp(ctx, freedrawEvent(0.1, 0))
    // Single-sample stroke → discarded.
    expect(store.size).toBe(0)
  })
})

describe('textTool', () => {
  it('creates an empty text element at the cursor and requests edit', async () => {
    const doc = new Y.Doc()
    const store = createElementStore(doc)
    const ctx = stubCtx(store)
    const { _resetEditBroker, onEditRequest } = await import('../text-editing')
    _resetEditBroker()
    let requested: string | null = null
    onEditRequest((id) => {
      requested = id
    })

    textTool.onPointerDown(ctx, makeEvent(20, 30))
    const el = store.list()[0]
    expect(el.type).toBe('text')
    expect((el as { text: string }).text).toBe('')
    expect(el.x).toBe(20)
    expect(el.y).toBe(30)
    expect(requested).toBe(el.id)
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
