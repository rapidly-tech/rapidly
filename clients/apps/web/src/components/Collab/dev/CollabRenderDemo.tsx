'use client'

/**
 * Collab v2 renderer demo page.
 *
 * Phase 3b adds selection + delete on top of the tool system:
 *  - Select tool: click / shift-click / marquee
 *  - Backspace or Delete removes all selected elements
 *  - Live bounding-box overlay on the interactive canvas
 *
 * All mutations still ride the ``ElementStore`` → Yjs → renderer
 * observe path production chambers will use.
 */

import { useCallback, useEffect, useRef, useState } from 'react'
import * as Y from 'yjs'

import {
  createElementStore,
  type ElementStore,
} from '@/utils/collab/element-store'
import { Renderer } from '@/utils/collab/renderer'
import { SelectionState } from '@/utils/collab/selection'
import { makeSelectionOverlay } from '@/utils/collab/selection-overlay'
import {
  currentMarqueeRect,
  hoverCursor,
  toolFor,
  type SelectToolCtx,
  type Tool,
  type ToolCtx,
  type ToolId,
} from '@/utils/collab/tools'
import { makeViewport, zoomAt, type Viewport } from '@/utils/collab/viewport'

function seedScene(store: ElementStore): void {
  store.transact(() => {
    store.create({
      type: 'rect',
      x: 100,
      y: 100,
      width: 160,
      height: 80,
      roundness: 12,
      strokeColor: '#1e1e1e',
      fillColor: '#fde68a',
      fillStyle: 'solid',
    })
    store.create({
      type: 'ellipse',
      x: 300,
      y: 120,
      width: 140,
      height: 100,
      strokeColor: '#1e40af',
      fillColor: '#dbeafe',
      fillStyle: 'solid',
    })
  })
}

const TOOL_CHOICES: Array<{ id: ToolId; label: string; hint: string }> = [
  { id: 'hand', label: 'Hand', hint: 'Drag to pan' },
  {
    id: 'select',
    label: 'Select',
    hint: 'Click, drag-move, handle-resize, marquee — Delete to remove',
  },
  { id: 'rect', label: 'Rect', hint: 'Drag to draw a rectangle' },
  { id: 'ellipse', label: 'Ellipse', hint: 'Drag to draw an ellipse' },
  { id: 'diamond', label: 'Diamond', hint: 'Drag to draw a diamond' },
  { id: 'line', label: 'Line', hint: 'Drag; shift snaps to 45°' },
  { id: 'arrow', label: 'Arrow', hint: 'Drag; shift snaps to 45°' },
  { id: 'freedraw', label: 'Pen', hint: 'Freehand stroke with pressure' },
  {
    id: 'text',
    label: 'Text',
    hint: 'Click to add text (inline editor is Phase 7b)',
  },
]

export function CollabRenderDemo() {
  const staticRef = useRef<HTMLCanvasElement | null>(null)
  const interactiveRef = useRef<HTMLCanvasElement | null>(null)
  const rendererRef = useRef<Renderer | null>(null)
  const storeRef = useRef<ElementStore | null>(null)
  const selectionRef = useRef<SelectionState>(new SelectionState())
  const activeToolRef = useRef<Tool | null>(null)
  const gestureToolRef = useRef<Tool | null>(null)
  const vpRef = useRef<Viewport>(makeViewport({ scrollX: -20, scrollY: -20 }))

  const [toolId, setToolId] = useState<ToolId>('hand')
  const [zoom, setZoom] = useState(1)
  const [elementCount, setElementCount] = useState(0)
  const [selectionSize, setSelectionSize] = useState(0)

  useEffect(() => {
    activeToolRef.current = toolFor(toolId)
  }, [toolId])

  useEffect(() => {
    const s = staticRef.current
    const i = interactiveRef.current
    if (!s || !i) return

    const doc = new Y.Doc()
    const store = createElementStore(doc)
    seedScene(store)
    storeRef.current = store
    setElementCount(store.size)

    const r = new Renderer({
      staticCanvas: s,
      interactiveCanvas: i,
      store,
      viewport: vpRef.current,
    })
    rendererRef.current = r

    const selection = selectionRef.current

    // Keep the selection pruned to live elements — a remote delete
    // that clobbers a selected element should drop it from our
    // selection too (matches §3.4 of the plan).
    const unobserveStore = store.observe(() => {
      setElementCount(store.size)
      const liveIds = new Set<string>()
      for (const el of store.list()) liveIds.add(el.id)
      selection.reconcile(liveIds)
    })

    const unsubscribeSelection = selection.subscribe((ids) => {
      setSelectionSize(ids.size)
      r.invalidate()
    })

    // Selection overlay paints the dashed bounding box + marquee.
    r.setInteractivePaint(
      makeSelectionOverlay({
        store,
        selection,
        getMarquee: () => currentMarqueeRect(),
        getViewport: () => r.getViewport(),
      }),
    )

    const onResize = () => r.resize()
    window.addEventListener('resize', onResize)
    return () => {
      window.removeEventListener('resize', onResize)
      unobserveStore()
      unsubscribeSelection()
      r.destroy()
      rendererRef.current = null
      storeRef.current = null
      doc.destroy()
    }
  }, [])

  const toolCtx = useCallback((): ToolCtx | null => {
    const renderer = rendererRef.current
    const store = storeRef.current
    if (!renderer || !store) return null
    const base: SelectToolCtx = {
      store,
      renderer,
      viewport: renderer.getViewport(),
      screenToWorld: (x, y) => renderer.screenToWorld(x, y),
      invalidate: () => renderer.invalidate(),
      selection: selectionRef.current,
    }
    return base
  }, [])

  const onPointerDown = useCallback(
    (e: React.PointerEvent) => {
      const canvas = interactiveRef.current
      const tool = activeToolRef.current
      const ctx = toolCtx()
      if (!canvas || !tool || !ctx) return
      canvas.setPointerCapture(e.pointerId)
      gestureToolRef.current = tool
      tool.onPointerDown(ctx, e.nativeEvent)
    },
    [toolCtx],
  )

  const [hoverCursorStyle, setHoverCursorStyle] = useState<string | null>(null)

  const onPointerMove = useCallback(
    (e: React.PointerEvent) => {
      const canvas = interactiveRef.current
      const tool = gestureToolRef.current
      const ctx = toolCtx()
      if (!tool || !ctx) {
        // No active gesture — if the select tool is active, see whether
        // the cursor sits over a handle so we can swap its cursor.
        if (canvas && toolId === 'select' && ctx === null) {
          setHoverCursorStyle(null)
        }
        if (toolId === 'select' && canvas) {
          const active = toolCtx()
          if (active) {
            const rect = canvas.getBoundingClientRect()
            const next = hoverCursor(
              active as SelectToolCtx,
              e.clientX - rect.left,
              e.clientY - rect.top,
              active.renderer
                ? (activeToolRef.current?.cursor ?? 'default')
                : 'default',
            )
            setHoverCursorStyle(next)
          }
        }
        return
      }
      tool.onPointerMove(ctx, e.nativeEvent)
    },
    [toolCtx, toolId],
  )

  const onPointerUp = useCallback(
    (e: React.PointerEvent) => {
      const canvas = interactiveRef.current
      const tool = gestureToolRef.current
      const ctx = toolCtx()
      gestureToolRef.current = null
      if (canvas && canvas.hasPointerCapture(e.pointerId)) {
        canvas.releasePointerCapture(e.pointerId)
      }
      if (!tool || !ctx) return
      tool.onPointerUp(ctx, e.nativeEvent)
      setZoom(Math.round(rendererRef.current!.getViewport().scale * 100) / 100)
    },
    [toolCtx],
  )

  const onWheel = useCallback((e: React.WheelEvent) => {
    e.preventDefault()
    const canvas = interactiveRef.current
    const renderer = rendererRef.current
    if (!canvas || !renderer) return
    const rect = canvas.getBoundingClientRect()
    const cx = e.clientX - rect.left
    const cy = e.clientY - rect.top
    const factor = Math.exp(-e.deltaY * 0.001)
    const next = zoomAt(
      renderer.getViewport(),
      cx,
      cy,
      renderer.getViewport().scale * factor,
    )
    vpRef.current = next
    renderer.setViewport(next)
    setZoom(Math.round(next.scale * 100) / 100)
  }, [])

  useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Delete' || e.key === 'Backspace') {
        const store = storeRef.current
        const selection = selectionRef.current
        if (!store || selection.size === 0) return
        // Avoid deleting form input fields elsewhere on the page —
        // our demo doesn't have any, but robust defence.
        const target = e.target as HTMLElement | null
        if (
          target &&
          (target.tagName === 'INPUT' || target.isContentEditable)
        ) {
          return
        }
        e.preventDefault()
        store.deleteMany(Array.from(selection.snapshot))
        selection.clear()
      } else if (e.key === 'Escape') {
        const tool = gestureToolRef.current
        const ctx = toolCtx()
        if (tool && ctx) tool.onCancel?.(ctx)
        gestureToolRef.current = null
        selectionRef.current.clear()
      }
    }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [toolCtx])

  const activeChoice = TOOL_CHOICES.find((t) => t.id === toolId)
  const cursor = hoverCursorStyle ?? activeToolRef.current?.cursor ?? 'default'

  return (
    <div className="flex h-screen w-screen flex-col bg-slate-50 dark:bg-slate-950">
      <div className="flex flex-wrap items-center gap-3 border-b border-slate-200 bg-white px-4 py-3 text-sm dark:border-slate-800 dark:bg-slate-900">
        <span className="font-semibold">Collab v2 demo</span>
        <div
          role="radiogroup"
          aria-label="Active tool"
          className="flex gap-1 rounded-lg bg-slate-100 p-1 dark:bg-slate-800"
        >
          {TOOL_CHOICES.map((t) => (
            <button
              key={t.id}
              type="button"
              role="radio"
              aria-checked={t.id === toolId}
              onClick={() => setToolId(t.id)}
              className={
                'rounded-md px-3 py-1 text-sm transition-colors ' +
                (t.id === toolId
                  ? 'bg-white text-slate-900 shadow-xs dark:bg-slate-700 dark:text-slate-50'
                  : 'rp-text-secondary hover:rp-text-primary')
              }
            >
              {t.label}
            </button>
          ))}
        </div>
        <span className="rp-text-secondary">{activeChoice?.hint}</span>
        <span className="ml-auto flex items-center gap-3">
          <span className="rp-text-secondary">
            elements:{' '}
            <span className="rp-text-primary font-mono">{elementCount}</span>
          </span>
          <span className="rp-text-secondary">
            selected:{' '}
            <span className="rp-text-primary font-mono">{selectionSize}</span>
          </span>
          <span className="rp-text-secondary">
            zoom:{' '}
            <span className="rp-text-primary font-mono">
              {zoom.toFixed(2)}×
            </span>
          </span>
        </span>
      </div>
      <div className="relative flex-1">
        <canvas
          ref={staticRef}
          className="absolute inset-0 h-full w-full"
          aria-hidden
        />
        <canvas
          ref={interactiveRef}
          onPointerDown={onPointerDown}
          onPointerMove={onPointerMove}
          onPointerUp={onPointerUp}
          onPointerCancel={onPointerUp}
          onWheel={onWheel}
          className="absolute inset-0 h-full w-full touch-none"
          style={{ cursor }}
          aria-label="Renderer demo canvas"
        />
      </div>
    </div>
  )
}
