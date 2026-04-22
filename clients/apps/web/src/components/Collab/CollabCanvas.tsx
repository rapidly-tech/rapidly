'use client'

/**
 * Collab whiteboard — canvas editor bound to ``Y.Array<Stroke>`` (PR 19).
 *
 * Interaction model
 * -----------------
 * Pointer-down starts a new stroke in local state (``inProgressRef``).
 * Every subsequent pointermove appends a point. Pointer-up (or leave)
 * commits the stroke by pushing a single entry into the shared Y.Array
 * — one update over the wire per stroke, not per point. Re-rendering
 * happens via ``observe`` on the Y.Array for remote strokes and via
 * ``requestAnimationFrame`` for the live local stroke.
 *
 * Why not broadcast each point?
 * -----------------------------
 * 60fps × multi-peer mesh = ~120 updates/sec/peer. Coalescing into one
 * entry per stroke keeps the wire quiet during heavy drawing; the
 * perception loss is small because a remote observer typically sees
 * each stroke as a completed shape anyway. A future PR could add a
 * ``pending_strokes`` awareness field for live-stroke previews if the
 * demo warrants it.
 */

import Button from '@rapidly-tech/ui/components/forms/Button'
import { useEffect, useRef, useState } from 'react'
import type * as Y from 'yjs'

import type { PresenceSource, RemotePresence } from '@/utils/collab/presence'
import { hueFor, isStroke, repaint, type Stroke } from '@/utils/collab/strokes'

interface CollabCanvasProps {
  doc: Y.Doc
  /** Our Yjs clientID for colour + author tagging. Pulled from the
   *  awareness module by the caller so the canvas stays decoupled. */
  clientID: number
  /** Optional Phase 11 ``PresenceSource`` so remote cursors render on
   *  top of the strokes. Absent → original single-user behaviour. */
  presence?: PresenceSource
  /** Publish the local cursor to remote peers. Called with ``null``
   *  when the pointer leaves the canvas so the cursor hides there. */
  publishCursor?: (point: { x: number; y: number } | null) => void
}

const DEFAULT_LINE_WIDTH = 3
const CANVAS_WIDTH = 1024
const CANVAS_HEIGHT = 600

export function CollabCanvas({
  doc,
  clientID,
  presence,
  publishCursor,
}: CollabCanvasProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const yStrokes = doc.getArray<Stroke>('strokes')
  const inProgressRef = useRef<Stroke | null>(null)
  // Mirror of the Y.Array held in a ref so the rAF-driven paint path
  // doesn't re-observe on every frame.
  const committedRef = useRef<Stroke[]>(
    yStrokes.toArray().filter(isStroke) as Stroke[],
  )
  const [committedCount, setCommittedCount] = useState<number>(
    committedRef.current.length,
  )

  // Remote / local Y.Array updates → refresh committedRef + force paint.
  useEffect(() => {
    const observer = () => {
      committedRef.current = yStrokes.toArray().filter(isStroke) as Stroke[]
      setCommittedCount(committedRef.current.length)
      paint()
    }
    yStrokes.observe(observer)
    // Initial paint.
    paint()
    return () => {
      yStrokes.unobserve(observer)
    }
  }, [yStrokes])

  // Committed-count change re-triggers paint even when the observer
  // path was skipped (first mount, edge cases).
  useEffect(() => {
    paint()
  }, [committedCount])

  // Remote-cursor repaint — subscribe to presence updates and repaint
  // on every change so cursors track at the presence source's own rate
  // (~60 Hz through awareness). No-op when ``presence`` isn't wired.
  useEffect(() => {
    if (!presence) return
    return presence.subscribe(() => paint())
  }, [presence])

  function paint(): void {
    const canvas = canvasRef.current
    if (!canvas) return
    const ctx = canvas.getContext('2d')
    if (!ctx) return
    repaint(
      ctx,
      canvas.width,
      canvas.height,
      committedRef.current,
      inProgressRef.current,
    )
    // Remote cursors ride on top of the committed + live strokes so a
    // peer's pointer always stays visible on a dense canvas.
    if (presence) {
      for (const remote of presence.getRemotes()) {
        paintRemoteCursor(ctx, remote)
      }
    }
  }

  /** Paint one remote peer's pointer as a coloured triangle in the
   *  peer's own colour. Name label — if present — rides to the right
   *  in a matching rounded pill. Coords are canvas-space (the stopgap
   *  CollabCanvas has no viewport / zoom). */
  function paintRemoteCursor(
    ctx: CanvasRenderingContext2D,
    remote: RemotePresence,
  ): void {
    const cursor = remote.cursor
    if (!cursor) return
    const size = 14
    ctx.save()
    ctx.translate(cursor.x, cursor.y)
    ctx.fillStyle = remote.user.color
    ctx.strokeStyle = 'rgba(0, 0, 0, 0.35)'
    ctx.lineWidth = 1
    ctx.lineJoin = 'round'
    ctx.beginPath()
    ctx.moveTo(0, 0)
    ctx.lineTo(size * 0.9, size * 0.35)
    ctx.lineTo(size * 0.35, size * 0.9)
    ctx.closePath()
    ctx.fill()
    ctx.stroke()
    if (remote.user.name) {
      const label = remote.user.name
      ctx.font = '11px system-ui, -apple-system, sans-serif'
      const metrics = ctx.measureText(label)
      const padX = 4
      const labelW = metrics.width + padX * 2
      const labelH = 14
      const lx = size * 0.9 + 6
      const ly = size * 0.35 - labelH / 2
      ctx.fillStyle = remote.user.color
      ctx.fillRect(lx, ly, labelW, labelH)
      ctx.fillStyle = '#ffffff'
      ctx.textBaseline = 'middle'
      ctx.fillText(label, lx + padX, ly + labelH / 2)
    }
    ctx.restore()
  }

  function canvasPoint(e: React.PointerEvent): [number, number] {
    const canvas = canvasRef.current
    if (!canvas) return [0, 0]
    const rect = canvas.getBoundingClientRect()
    // Scale from displayed CSS pixels to the canvas's internal pixel
    // dimensions — the canvas backing buffer is fixed-size for
    // deterministic coordinate broadcast.
    const scaleX = canvas.width / rect.width
    const scaleY = canvas.height / rect.height
    return [(e.clientX - rect.left) * scaleX, (e.clientY - rect.top) * scaleY]
  }

  function onPointerDown(e: React.PointerEvent<HTMLCanvasElement>): void {
    e.currentTarget.setPointerCapture(e.pointerId)
    const [x, y] = canvasPoint(e)
    inProgressRef.current = {
      by: String(clientID),
      pts: [x, y],
      hue: hueFor(clientID),
      w: DEFAULT_LINE_WIDTH,
    }
    paint()
  }

  function onPointerMove(e: React.PointerEvent<HTMLCanvasElement>): void {
    const [x, y] = canvasPoint(e)
    // Publish the local cursor every move so hovering (not just
    // drawing) shows up for peers. Skipped when no publisher is
    // wired — the stopgap single-user path stays identical.
    publishCursor?.({ x, y })
    const stroke = inProgressRef.current
    if (!stroke) return
    stroke.pts.push(x, y)
    paint()
  }

  function onPointerUp(e: React.PointerEvent<HTMLCanvasElement>): void {
    const stroke = inProgressRef.current
    if (!stroke) {
      // Pointer left the canvas without drawing — still clear the
      // published cursor so peers don't see a ghost pointer.
      if (e.type === 'pointerleave' || e.type === 'pointercancel') {
        publishCursor?.(null)
      }
      return
    }
    try {
      e.currentTarget.releasePointerCapture(e.pointerId)
    } catch {
      /* some platforms throw if the capture was already released */
    }
    // Commit: single Y.Array push = one CRDT update = one wire frame.
    doc.transact(() => {
      yStrokes.push([stroke])
    })
    inProgressRef.current = null
    if (e.type === 'pointerleave') publishCursor?.(null)
    // The observer will repaint, but fire one now so the end-of-stroke
    // visual lands immediately on slow peers.
    paint()
  }

  function onClear(): void {
    // Yjs delete on a shared array is a CRDT op — every peer sees it.
    if (yStrokes.length === 0) return
    doc.transact(() => {
      yStrokes.delete(0, yStrokes.length)
    })
  }

  return (
    <div className="flex w-full flex-col gap-3">
      <div className="flex items-center justify-between">
        <p className="rp-text-muted text-xs">
          Draw anywhere. Every stroke appears on every peer&apos;s canvas as
          soon as you lift the pointer.
        </p>
        <Button variant="outline" size="sm" onClick={onClear}>
          Clear
        </Button>
      </div>
      <canvas
        ref={canvasRef}
        width={CANVAS_WIDTH}
        height={CANVAS_HEIGHT}
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={onPointerUp}
        onPointerCancel={onPointerUp}
        onPointerLeave={onPointerUp}
        className="glass-elevated h-auto w-full touch-none rounded-2xl border border-(--beige-border)/30 bg-white shadow-xs dark:border-white/6 dark:bg-white/3"
        style={{ aspectRatio: `${CANVAS_WIDTH} / ${CANVAS_HEIGHT}` }}
      />
    </div>
  )
}
