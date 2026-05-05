'use client'

/**
 * Bottom-right corner minimap. Renders a low-fidelity overview of
 * every element on the scene plus a rectangle showing the viewport.
 * Click anywhere on the minimap to centre the viewport on that
 * world point; drag to pan continuously.
 *
 * Drawn to an off-screen canvas with rough rect/ellipse silhouettes —
 * no rough.js style, no text — so the cost is roughly O(elements).
 * Re-renders fire whenever ``elements`` or ``viewport`` change.
 */

import { useCallback, useEffect, useRef } from 'react'

import type { CollabElement } from '@/utils/collab/elements'
import {
  centreViewportOn,
  computeSceneBounds,
  minimapPointToWorld,
  projectRect,
  projectToMinimap,
  projectViewportRect,
} from '@/utils/collab/minimap'
import type { Viewport } from '@/utils/collab/viewport'

interface Props {
  elements: CollabElement[]
  viewport: Viewport
  /** Live size of the main interactive canvas — needed so the
   *  viewport rectangle scales to the user's actual window. */
  canvasWidth: number
  canvasHeight: number
  /** Apply a new viewport (after click-to-pan / drag-to-pan). */
  onViewportChange: (next: Viewport) => void
}

const MAP_WIDTH = 180
const MAP_HEIGHT = 120

export function Minimap({
  elements,
  viewport,
  canvasWidth,
  canvasHeight,
  onViewportChange,
}: Props) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null)
  const draggingRef = useRef(false)

  // Paint pass — silhouettes + viewport rect.
  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const ctx = canvas.getContext('2d')
    if (!ctx) return
    const dpr = window.devicePixelRatio || 1
    if (canvas.width !== MAP_WIDTH * dpr) {
      canvas.width = MAP_WIDTH * dpr
      canvas.height = MAP_HEIGHT * dpr
    }
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
    ctx.clearRect(0, 0, MAP_WIDTH, MAP_HEIGHT)

    // Background — slate-50 / slate-900 depending on the host theme.
    const isDark = document.documentElement.classList.contains('dark')
    ctx.fillStyle = isDark ? '#0f172a' : '#f8fafc'
    ctx.fillRect(0, 0, MAP_WIDTH, MAP_HEIGHT)

    const bounds = computeSceneBounds(elements)
    const proj = projectToMinimap(bounds, MAP_WIDTH, MAP_HEIGHT, 6)

    // Element silhouettes.
    ctx.fillStyle = isDark ? '#334155' : '#cbd5e1'
    for (const el of elements) {
      const r = projectRect(
        { x: el.x, y: el.y, width: el.width, height: el.height },
        proj,
      )
      // Tiny floor so a 0×0 element is still visible.
      const w = Math.max(1, r.width)
      const h = Math.max(1, r.height)
      if (el.type === 'ellipse') {
        ctx.beginPath()
        ctx.ellipse(r.x + w / 2, r.y + h / 2, w / 2, h / 2, 0, 0, Math.PI * 2)
        ctx.fill()
      } else {
        ctx.fillRect(r.x, r.y, w, h)
      }
    }

    // Viewport rect on top.
    const vp = projectViewportRect(viewport, canvasWidth, canvasHeight, proj)
    ctx.strokeStyle = isDark ? '#a5d8ff' : '#1d4ed8'
    ctx.lineWidth = 1.5
    ctx.strokeRect(vp.x, vp.y, vp.width, vp.height)
    ctx.fillStyle = isDark ? 'rgba(165,216,255,0.10)' : 'rgba(29,78,216,0.10)'
    ctx.fillRect(vp.x, vp.y, vp.width, vp.height)
  }, [elements, viewport, canvasWidth, canvasHeight])

  // Map a click/drag in minimap-space to a viewport recentre.
  const focusFromEvent = useCallback(
    (e: { clientX: number; clientY: number }) => {
      const canvas = canvasRef.current
      if (!canvas) return
      const rect = canvas.getBoundingClientRect()
      const mx = e.clientX - rect.left
      const my = e.clientY - rect.top
      const bounds = computeSceneBounds(elements)
      const proj = projectToMinimap(bounds, MAP_WIDTH, MAP_HEIGHT, 6)
      const world = minimapPointToWorld(mx, my, proj)
      onViewportChange(
        centreViewportOn(viewport, world.x, world.y, canvasWidth, canvasHeight),
      )
    },
    [elements, viewport, canvasWidth, canvasHeight, onViewportChange],
  )

  return (
    <div
      className="pointer-events-auto fixed right-4 bottom-4 z-30 rounded-lg border border-slate-200 bg-white shadow-md dark:border-slate-700 dark:bg-slate-900"
      aria-label="Whiteboard minimap"
    >
      <canvas
        ref={canvasRef}
        width={MAP_WIDTH}
        height={MAP_HEIGHT}
        style={{ width: MAP_WIDTH, height: MAP_HEIGHT }}
        className="block cursor-crosshair rounded-lg"
        onPointerDown={(e) => {
          draggingRef.current = true
          ;(e.target as Element).setPointerCapture?.(e.pointerId)
          focusFromEvent(e)
        }}
        onPointerMove={(e) => {
          if (!draggingRef.current) return
          focusFromEvent(e)
        }}
        onPointerUp={(e) => {
          draggingRef.current = false
          ;(e.target as Element).releasePointerCapture?.(e.pointerId)
        }}
      />
    </div>
  )
}
