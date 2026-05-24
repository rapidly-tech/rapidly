/**
 * Freedraw (pen) tool.
 *
 * Pointer-down starts a new stroke. Every pointer-move appends a
 * ``(x, y, pressure)`` sample into the shared ``points`` array; the
 * AABB is kept in sync so the renderer's rotation anchor + the
 * select tool's AABB-based marquee both read the right bounds.
 *
 * Each sample is committed via ``store.update`` — the element exists
 * in the CRDT from the first sample so remote peers see the stroke
 * grow live (important for the collab feel). The perf cost of many
 * small updates is acceptable for freedraw; if it becomes a problem
 * we can batch into an ``updateMany`` tick but at 60-120 Hz pointer
 * events most browsers throttle anyway.
 */

import {
  readReportedPressure,
  simulatePressureFromVelocity,
  smoothPressure,
} from '../pressure'
import type { Tool, ToolCtx } from './types'

const MIN_SAMPLES = 2
const MIN_POINTER_DELTA = 0.5

interface DrawState {
  id: string
  /** Canonical world-space points the tool has committed so far.
   *  Rebuilt at the AABB's origin on each sample before writing. */
  worldSamples: Array<{ x: number; y: number; p: number }>
  /** Timestamp of the most recent sample — feeds the velocity-based
   *  pressure simulator on devices that don't report real pressure
   *  (mouse, most capacitive touch). */
  lastT: number
  /** Smoothed simulated pressure so a single velocity blip doesn't
   *  cut a one-sample ink thinning into the stroke. */
  simulatedP: number
  /** True when the device reports real pressure (pen / stylus). We
   *  pin this at gesture start so a tap mid-stroke can't flip modes. */
  useReported: boolean
}

let state: DrawState | null = null

export const freedrawTool: Tool = {
  id: 'freedraw',
  cursor: 'crosshair',

  onPointerDown(ctx, e) {
    const { x, y } = worldPoint(ctx, e)
    const reported = readReportedPressure(e)
    const useReported = reported !== null
    // First sample — no velocity history yet. Pin to reported pressure
    // when available; otherwise seed at the mid-simulated value so the
    // stroke starts at a reasonable weight.
    const startPressure = useReported ? reported : 0.55
    const now =
      typeof performance !== 'undefined' ? performance.now() : Date.now()
    const id = ctx.store.create({
      type: 'freedraw',
      x,
      y,
      width: 0,
      height: 0,
      points: [0, 0, startPressure],
      simulatePressure: !useReported,
    })
    state = {
      id,
      worldSamples: [{ x, y, p: startPressure }],
      lastT: now,
      simulatedP: startPressure,
      useReported,
    }
  },

  onPointerMove(ctx, e) {
    if (!state) return
    const { x, y } = worldPoint(ctx, e)

    const last = state.worldSamples[state.worldSamples.length - 1]
    if (Math.hypot(x - last.x, y - last.y) < MIN_POINTER_DELTA) return

    // Pressure: read reported on pen, simulate from velocity otherwise.
    // The ``useReported`` flag is pinned at gesture start so the curve
    // doesn't flip if a browser inconsistently reports pressure mid-
    // stroke.
    const now =
      typeof performance !== 'undefined' ? performance.now() : Date.now()
    let pressure: number
    if (state.useReported) {
      pressure = readReportedPressure(e) ?? state.simulatedP
    } else {
      const target = simulatePressureFromVelocity(
        { x: last.x, y: last.y, t: state.lastT },
        { x, y, t: now },
      )
      pressure = smoothPressure(state.simulatedP, target)
      state.simulatedP = pressure
    }
    state.lastT = now

    state.worldSamples.push({ x, y, p: pressure })
    ctx.store.update(state.id, rebuild(state.worldSamples))
  },

  onPointerUp(ctx) {
    if (!state) return
    const sampleCount = state.worldSamples.length
    const id = state.id
    state = null
    if (sampleCount < MIN_SAMPLES) {
      ctx.store.delete(id)
    }
  },

  onCancel(ctx) {
    if (!state) return
    ctx.store.delete(state.id)
    state = null
  },
}

function worldPoint(ctx: ToolCtx, e: PointerEvent): { x: number; y: number } {
  const rect = (e.target as HTMLElement).getBoundingClientRect()
  return ctx.screenToWorld(e.clientX - rect.left, e.clientY - rect.top)
}

/** Rebuild the ``{x, y, width, height, points}`` patch from the
 *  world-space sample buffer. Keeps the element's origin + AABB in
 *  sync with the points as the stroke grows. */
function rebuild(samples: ReadonlyArray<{ x: number; y: number; p: number }>): {
  x: number
  y: number
  width: number
  height: number
  points: number[]
} {
  let minX = Infinity
  let minY = Infinity
  let maxX = -Infinity
  let maxY = -Infinity
  for (const s of samples) {
    if (s.x < minX) minX = s.x
    if (s.y < minY) minY = s.y
    if (s.x > maxX) maxX = s.x
    if (s.y > maxY) maxY = s.y
  }
  const width = Math.max(0, maxX - minX)
  const height = Math.max(0, maxY - minY)
  const points: number[] = []
  for (const s of samples) {
    points.push(s.x - minX, s.y - minY, s.p)
  }
  return { x: minX, y: minY, width, height, points }
}
