'use client'

/**
 * Collab v2 renderer perf harness.
 *
 * Purpose
 * -------
 * Before Phase 1 commits to "native Canvas 2D renderer", this page
 * answers one question: **does drawing 5000 simple elements + panning
 * + zooming sustain 60fps on a typical laptop?** If yes, the Phase 1
 * architecture holds. If no, we pivot to OffscreenCanvas + a render
 * worker — a much bigger Phase 1.
 *
 * How it measures
 * ---------------
 * - We build 5000 rects in a real ``ElementStore`` (same API the
 *   production renderer will use). Coordinates span a 10k × 10k
 *   world.
 * - A single canvas paints every element each frame. (Phase 1 will
 *   split static + interactive canvases; here we deliberately use
 *   the pessimistic one-canvas-paint-everything model to stress the
 *   render loop.)
 * - A requestAnimationFrame loop walks the store, paints, and
 *   records the frame's wall time. A 60-frame rolling window gives
 *   the displayed fps.
 * - The user pans with pointer-drag and zooms with the wheel. Paint
 *   happens on every frame regardless (always-on loop) so the
 *   number you see *is* the steady-state cost — we don't cheat by
 *   skipping frames when nothing changed.
 *
 * Decision rule
 * -------------
 * - ≥ 55fps sustained: Phase 1 can use plain Canvas 2D. GREEN.
 * - 30-55fps: two-canvas split + hit-cache should push us over;
 *   keep Canvas 2D but budget 0.5 week of optimisation. AMBER.
 * - < 30fps: pivot to OffscreenCanvas + Worker; Phase 1 grows ~3×. RED.
 *
 * What this harness is **not**
 * ----------------------------
 * - Not the production renderer — no hand-drawn look, no shape
 *   types other than rect, no hit testing. Adding any of those
 *   slows the number; the question here is the *floor* performance.
 */

import { useCallback, useEffect, useMemo, useRef, useState } from 'react'

import {
  createElementStore,
  type ElementStore,
} from '@/utils/collab/element-store'
import type { CollabElement } from '@/utils/collab/elements'
import * as Y from 'yjs'

const WORLD_SIZE = 10_000
const RECT_MIN = 20
const RECT_MAX = 100

/** Deterministic pseudo-random so we measure the same scene across
 *  runs. xmur3 + mulberry32 — a standard tiny PRNG pair. */
function makePRNG(seed: string): () => number {
  let h = 1779033703 ^ seed.length
  for (let i = 0; i < seed.length; i++) {
    h = Math.imul(h ^ seed.charCodeAt(i), 3432918353)
    h = (h << 13) | (h >>> 19)
  }
  let a = h >>> 0
  return () => {
    a = (a + 0x6d2b79f5) >>> 0
    let t = a
    t = Math.imul(t ^ (t >>> 15), t | 1)
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61)
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296
  }
}

function seedScene(store: ElementStore, n: number): void {
  const rand = makePRNG('collab-perf-v1')
  store.transact(() => {
    for (let i = 0; i < n; i++) {
      const w = RECT_MIN + rand() * (RECT_MAX - RECT_MIN)
      const h = RECT_MIN + rand() * (RECT_MAX - RECT_MIN)
      store.create({
        type: 'rect',
        x: rand() * (WORLD_SIZE - w),
        y: rand() * (WORLD_SIZE - h),
        width: w,
        height: h,
        roundness: 0,
        // Override the random seed so the scene is fully reproducible.
        seed: Math.floor(rand() * 2 ** 31),
        zIndex: i,
        strokeColor: `hsl(${Math.floor(rand() * 360)} 70% 45%)`,
      })
    }
  })
}

interface Viewport {
  scale: number
  scrollX: number
  scrollY: number
}

function paint(
  ctx: CanvasRenderingContext2D,
  elements: readonly CollabElement[],
  viewport: Viewport,
  canvasWidth: number,
  canvasHeight: number,
): void {
  ctx.setTransform(1, 0, 0, 1, 0, 0)
  ctx.fillStyle = '#fafaf6'
  ctx.fillRect(0, 0, canvasWidth, canvasHeight)

  ctx.setTransform(
    viewport.scale,
    0,
    0,
    viewport.scale,
    -viewport.scrollX * viewport.scale,
    -viewport.scrollY * viewport.scale,
  )

  // Axis-aligned rects only — no rotation, no rough style. Stress the
  // render loop, not the per-shape cost.
  for (let i = 0; i < elements.length; i++) {
    const el = elements[i]
    if (el.type !== 'rect') continue
    ctx.strokeStyle = el.strokeColor
    ctx.lineWidth = el.strokeWidth
    ctx.strokeRect(el.x, el.y, el.width, el.height)
  }
}

const ELEMENT_COUNTS = [500, 1000, 2500, 5000, 10_000] as const

export function CollabPerfHarness() {
  const canvasRef = useRef<HTMLCanvasElement | null>(null)
  const storeRef = useRef<ElementStore | null>(null)
  const docRef = useRef<Y.Doc | null>(null)
  const elementsRef = useRef<readonly CollabElement[]>([])
  const viewportRef = useRef<Viewport>({ scale: 1, scrollX: 0, scrollY: 0 })
  const rafRef = useRef<number | null>(null)
  const frameTimesRef = useRef<number[]>([])

  const [elementCount, setElementCount] = useState(5000)
  const [fps, setFps] = useState(0)
  const [frameMs, setFrameMs] = useState(0)
  const [paintedElements, setPaintedElements] = useState(0)
  const [scale, setScale] = useState(1)

  // Build the scene whenever the target count changes.
  useEffect(() => {
    const doc = new Y.Doc()
    const store = createElementStore(doc)
    seedScene(store, elementCount)
    docRef.current = doc
    storeRef.current = store
    elementsRef.current = store.list()
    setPaintedElements(elementsRef.current.length)
    // Reset viewport when scene changes so the 10k×10k world is
    // centred in the canvas.
    const canvas = canvasRef.current
    if (canvas) {
      viewportRef.current = {
        scale: 1,
        scrollX: (WORLD_SIZE - canvas.clientWidth) / 2,
        scrollY: (WORLD_SIZE - canvas.clientHeight) / 2,
      }
      setScale(1)
    }
    return () => {
      doc.destroy()
    }
  }, [elementCount])

  // Render loop — always on so the displayed fps is the steady-state
  // cost, not a peak-during-interaction number.
  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const ctx = canvas.getContext('2d')
    if (!ctx) return

    const dpr = window.devicePixelRatio || 1
    const resize = () => {
      const rect = canvas.getBoundingClientRect()
      canvas.width = Math.floor(rect.width * dpr)
      canvas.height = Math.floor(rect.height * dpr)
      ctx.scale(dpr, dpr)
    }
    resize()

    const loop = () => {
      const start = performance.now()
      const rect = canvas.getBoundingClientRect()
      paint(
        ctx,
        elementsRef.current,
        viewportRef.current,
        rect.width,
        rect.height,
      )
      const dt = performance.now() - start

      const buf = frameTimesRef.current
      buf.push(dt)
      if (buf.length > 60) buf.shift()
      rafRef.current = requestAnimationFrame(loop)
    }
    rafRef.current = requestAnimationFrame(loop)

    const fpsTick = setInterval(() => {
      const buf = frameTimesRef.current
      if (buf.length === 0) return
      const avg = buf.reduce((s, v) => s + v, 0) / buf.length
      setFrameMs(Math.round(avg * 10) / 10)
      // Cap at 60fps — every browser clamps RAF there. Over-reporting
      // would be misleading.
      setFps(Math.min(60, Math.round(1000 / Math.max(1, avg))))
    }, 250)

    return () => {
      if (rafRef.current != null) cancelAnimationFrame(rafRef.current)
      clearInterval(fpsTick)
    }
  }, [])

  // Pan with pointer-drag, zoom at cursor with wheel.
  const onPointerDown = useCallback((e: React.PointerEvent) => {
    const canvas = canvasRef.current
    if (!canvas) return
    canvas.setPointerCapture(e.pointerId)
    const startX = e.clientX
    const startY = e.clientY
    const startVP = { ...viewportRef.current }
    const onMove = (ev: PointerEvent) => {
      viewportRef.current = {
        ...startVP,
        scrollX: startVP.scrollX - (ev.clientX - startX) / startVP.scale,
        scrollY: startVP.scrollY - (ev.clientY - startY) / startVP.scale,
      }
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
    const canvas = canvasRef.current
    if (!canvas) return
    const rect = canvas.getBoundingClientRect()
    const mx = e.clientX - rect.left
    const my = e.clientY - rect.top
    const factor = Math.exp(-e.deltaY * 0.001)
    const vp = viewportRef.current
    const nextScale = Math.max(0.05, Math.min(10, vp.scale * factor))
    // Anchor zoom at the cursor: world coord under cursor stays fixed.
    const worldX = vp.scrollX + mx / vp.scale
    const worldY = vp.scrollY + my / vp.scale
    viewportRef.current = {
      scale: nextScale,
      scrollX: worldX - mx / nextScale,
      scrollY: worldY - my / nextScale,
    }
    setScale(Math.round(nextScale * 100) / 100)
  }, [])

  const verdict = useMemo(() => {
    if (fps >= 55)
      return { label: 'GREEN · Canvas 2D is fine', tone: 'good' as const }
    if (fps >= 30)
      return { label: 'AMBER · needs optimisation', tone: 'warn' as const }
    return { label: 'RED · pivot to OffscreenCanvas', tone: 'bad' as const }
  }, [fps])

  const verdictClass =
    verdict.tone === 'good'
      ? 'bg-emerald-50 text-emerald-900 dark:bg-emerald-950/40 dark:text-emerald-100'
      : verdict.tone === 'warn'
        ? 'bg-amber-50 text-amber-900 dark:bg-amber-950/40 dark:text-amber-100'
        : 'bg-red-50 text-red-900 dark:bg-red-950/40 dark:text-red-100'

  return (
    <div className="flex h-screen w-screen flex-col bg-slate-50 dark:bg-slate-950">
      <div className="flex items-center gap-4 border-b border-slate-200 bg-white px-4 py-3 text-sm dark:border-slate-800 dark:bg-slate-900">
        <span className="font-semibold">Collab v2 perf harness</span>
        <select
          value={elementCount}
          onChange={(e) => setElementCount(Number(e.target.value))}
          className="rounded-md border border-slate-300 bg-white px-2 py-1 dark:border-slate-700 dark:bg-slate-800"
        >
          {ELEMENT_COUNTS.map((n) => (
            <option key={n} value={n}>
              {n.toLocaleString()} elements
            </option>
          ))}
        </select>
        <span className="rp-text-secondary">
          Drag to pan, scroll to zoom (
          <span className="font-mono">{scale.toFixed(2)}×</span>)
        </span>
        <span className="ml-auto flex items-center gap-3">
          <span className="rp-text-secondary">
            painted:{' '}
            <span className="rp-text-primary font-mono">
              {paintedElements.toLocaleString()}
            </span>
          </span>
          <span className="rp-text-secondary">
            frame:{' '}
            <span className="rp-text-primary font-mono">{frameMs} ms</span>
          </span>
          <span className="rp-text-secondary">
            fps: <span className="rp-text-primary font-mono">{fps}</span>
          </span>
          <span
            className={`rounded-full px-3 py-1 text-xs font-medium ${verdictClass}`}
          >
            {verdict.label}
          </span>
        </span>
      </div>
      <canvas
        ref={canvasRef}
        onPointerDown={onPointerDown}
        onWheel={onWheel}
        className="flex-1 cursor-grab touch-none active:cursor-grabbing"
        aria-label="Perf harness canvas"
      />
    </div>
  )
}
