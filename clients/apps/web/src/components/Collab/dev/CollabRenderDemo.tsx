'use client'

/**
 * Collab v2 renderer demo page.
 *
 * Minimal Phase 1b proof-point: mount a ``Renderer`` over a local
 * ``ElementStore`` seeded with a handful of rects + ellipses, and
 * verify pan / zoom / hit-test work end-to-end. No tools, no mesh,
 * no E2EE — just the rendering pipeline driving real canvases.
 *
 * Clicking an element logs the hit id into the HUD. This is the
 * contract Phase 3 (draw + select + delete) will build on top of.
 */

import { useCallback, useEffect, useRef, useState } from 'react'
import * as Y from 'yjs'

import {
  createElementStore,
  type ElementStore,
} from '@/utils/collab/element-store'
import { Renderer } from '@/utils/collab/renderer'
import {
  makeViewport,
  panByScreen,
  zoomAt,
  type Viewport,
} from '@/utils/collab/viewport'

function seedScene(store: ElementStore): void {
  // A deliberately small, hand-picked scene. The perf harness at
  // ``/dev/collab-perf`` is the place to prove scale; this page is
  // for correctness.
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
      type: 'rect',
      x: 320,
      y: 160,
      width: 120,
      height: 120,
      roundness: 0,
      angle: Math.PI / 12,
      strokeColor: '#166534',
      fillColor: '#bbf7d0',
      fillStyle: 'solid',
      strokeWidth: 3,
    })
    store.create({
      type: 'ellipse',
      x: 160,
      y: 260,
      width: 200,
      height: 120,
      strokeColor: '#9d174d',
      fillColor: 'transparent',
      strokeWidth: 2,
      strokeStyle: 'dashed',
    })
    store.create({
      type: 'ellipse',
      x: 420,
      y: 40,
      width: 140,
      height: 140,
      strokeColor: '#1e40af',
      fillColor: '#dbeafe',
      fillStyle: 'solid',
    })
    store.create({
      type: 'rect',
      x: 560,
      y: 220,
      width: 180,
      height: 100,
      roundness: 24,
      strokeColor: '#7c2d12',
      fillColor: 'transparent',
      strokeWidth: 4,
      strokeStyle: 'dotted',
    })
  })
}

export function CollabRenderDemo() {
  const staticRef = useRef<HTMLCanvasElement | null>(null)
  const interactiveRef = useRef<HTMLCanvasElement | null>(null)
  const rendererRef = useRef<Renderer | null>(null)
  const vpRef = useRef<Viewport>(makeViewport({ scrollX: -20, scrollY: -20 }))
  const [zoom, setZoom] = useState(1)
  const [hitId, setHitId] = useState<string | null>(null)
  const [elementCount, setElementCount] = useState(0)

  useEffect(() => {
    const s = staticRef.current
    const i = interactiveRef.current
    if (!s || !i) return

    const doc = new Y.Doc()
    const store = createElementStore(doc)
    seedScene(store)
    setElementCount(store.size)

    const r = new Renderer({
      staticCanvas: s,
      interactiveCanvas: i,
      store,
      viewport: vpRef.current,
    })
    rendererRef.current = r

    const onResize = () => r.resize()
    window.addEventListener('resize', onResize)
    return () => {
      window.removeEventListener('resize', onResize)
      r.destroy()
      rendererRef.current = null
      doc.destroy()
    }
  }, [])

  const onPointerDown = useCallback((e: React.PointerEvent) => {
    const canvas = interactiveRef.current
    const renderer = rendererRef.current
    if (!canvas || !renderer) return

    const rect = canvas.getBoundingClientRect()
    const cx = e.clientX - rect.left
    const cy = e.clientY - rect.top
    const world = renderer.screenToWorld(cx, cy)
    setHitId(renderer.hitTest(world.x, world.y))

    // Begin a pan drag.
    canvas.setPointerCapture(e.pointerId)
    const startX = e.clientX
    const startY = e.clientY
    const startVP = { ...vpRef.current }
    const onMove = (ev: PointerEvent) => {
      vpRef.current = panByScreen(
        startVP,
        ev.clientX - startX,
        ev.clientY - startY,
      )
      renderer.setViewport(vpRef.current)
    }
    const onUp = (ev: PointerEvent) => {
      canvas.removeEventListener('pointermove', onMove)
      canvas.removeEventListener('pointerup', onUp)
      canvas.releasePointerCapture(ev.pointerId)
    }
    canvas.addEventListener('pointermove', onMove)
    canvas.addEventListener('pointerup', onUp)
  }, [])

  const onWheel = useCallback((e: React.WheelEvent) => {
    e.preventDefault()
    const canvas = interactiveRef.current
    const renderer = rendererRef.current
    if (!canvas || !renderer) return
    const rect = canvas.getBoundingClientRect()
    const cx = e.clientX - rect.left
    const cy = e.clientY - rect.top
    const factor = Math.exp(-e.deltaY * 0.001)
    const next = zoomAt(vpRef.current, cx, cy, vpRef.current.scale * factor)
    vpRef.current = next
    renderer.setViewport(next)
    setZoom(Math.round(next.scale * 100) / 100)
  }, [])

  return (
    <div className="flex h-screen w-screen flex-col bg-slate-50 dark:bg-slate-950">
      <div className="flex items-center gap-4 border-b border-slate-200 bg-white px-4 py-3 text-sm dark:border-slate-800 dark:bg-slate-900">
        <span className="font-semibold">Collab v2 renderer demo</span>
        <span className="rp-text-secondary">
          Drag to pan · scroll to zoom (
          <span className="font-mono">{zoom.toFixed(2)}×</span>)
        </span>
        <span className="ml-auto flex items-center gap-3">
          <span className="rp-text-secondary">
            elements:{' '}
            <span className="rp-text-primary font-mono">{elementCount}</span>
          </span>
          <span className="rp-text-secondary">
            hit:{' '}
            <span className="rp-text-primary font-mono">{hitId ?? 'none'}</span>
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
          onWheel={onWheel}
          className="absolute inset-0 h-full w-full cursor-grab touch-none active:cursor-grabbing"
          aria-label="Renderer demo canvas"
        />
      </div>
    </div>
  )
}
