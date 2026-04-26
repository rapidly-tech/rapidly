/**
 * Scene export for the Collab v2 whiteboard.
 *
 * Two formats, one surface:
 *
 *  - **JSON** — a versioned wrapper around the raw element list. The
 *    shape is the ""Rapidly dialect"" referenced in the plan: schema
 *    marker + version + elements array. Good for re-importing into
 *    another Rapidly canvas and for archiving. Same element shape
 *    the Yjs doc holds; no field filtering.
 *  - **PNG** — rasterised snapshot of the scene bounds, rendered
 *    through the existing ``shapes/`` adapters so the export looks
 *    pixel-identical to the live canvas.
 *
 * Everything in this module is synchronous except the PNG blob
 * encode, which goes via ``HTMLCanvasElement.toBlob``. The canvas
 * factory is injectable so tests can stub it; production callers let
 * it default to ``document.createElement``.
 *
 * Scope
 * -----
 * SVG export is a natural follow-up but needs every shape adapter to
 * emit SVG paths as a side channel; deferred so this PR stays
 * focused on the two formats people actually reach for first.
 */

import type { CollabElement } from './elements'
import { adapterFor } from './shapes'

// ── JSON ────────────────────────────────────────────────────────────

export const EXPORT_SCHEMA = 'rapidly-collab-v1' as const

export interface ExportedScene {
  schema: typeof EXPORT_SCHEMA
  version: 1
  /** Elements in paint order (low-z first). Import preserves this. */
  elements: CollabElement[]
}

/** Wrap an element list in the versioned export envelope. Pure; the
 *  caller serialises via ``JSON.stringify`` when it's ready to write. */
export function exportToJSON(
  elements: readonly CollabElement[],
): ExportedScene {
  return {
    schema: EXPORT_SCHEMA,
    version: 1,
    // Clone by value so later store edits don't leak into an already-
    // exported payload (matches clipboard behaviour).
    elements: elements.map((el) => structuredClone(el)),
  }
}

// ── Bounds ──────────────────────────────────────────────────────────

export interface Bounds {
  x: number
  y: number
  width: number
  height: number
}

/** Axis-aligned bounding box covering every element in the list.
 *  Returns ``null`` on empty input — the PNG exporter short-circuits
 *  in that case since a 0×0 canvas is meaningless. */
export function computeBounds(
  elements: readonly CollabElement[],
): Bounds | null {
  if (elements.length === 0) return null
  let minX = Infinity
  let minY = Infinity
  let maxX = -Infinity
  let maxY = -Infinity
  for (const el of elements) {
    if (el.x < minX) minX = el.x
    if (el.y < minY) minY = el.y
    const ex = el.x + el.width
    const ey = el.y + el.height
    if (ex > maxX) maxX = ex
    if (ey > maxY) maxY = ey
  }
  return {
    x: minX,
    y: minY,
    width: maxX - minX,
    height: maxY - minY,
  }
}

// ── Painter ─────────────────────────────────────────────────────────

export interface PaintOptions {
  /** World origin mapped to canvas pixel 0 — subtract from element x.
   *  The PNG exporter sets this to the bounds origin so the scene
   *  sits flush at the canvas edge before padding. */
  offsetX: number
  offsetY: number
  /** Rendering scale. 1 = 1 world unit → 1 canvas pixel. Higher values
   *  produce sharper exports at the cost of blob size. */
  scale: number
}

/** Paint every element onto ``ctx`` through the shape registry.
 *  Skips unknown types rather than throwing — matches renderer
 *  behaviour so a forward-compat element from a newer peer doesn't
 *  corrupt the export. */
export function paintElementsOnto(
  ctx: CanvasRenderingContext2D,
  elements: readonly CollabElement[],
  options: PaintOptions,
): void {
  ctx.save()
  // Scale once, translate by the negative offset in world units.
  ctx.scale(options.scale, options.scale)
  ctx.translate(-options.offsetX, -options.offsetY)
  for (const el of elements) {
    const adapter = adapterFor(el)
    if (!adapter) continue
    const path = adapter.pathFor(el)
    ctx.save()
    ctx.translate(el.x, el.y)
    if (el.angle !== 0) {
      const cx = el.width / 2
      const cy = el.height / 2
      ctx.translate(cx, cy)
      ctx.rotate(el.angle)
      ctx.translate(-cx, -cy)
    }
    adapter.paint(ctx, el, path)
    ctx.restore()
  }
  ctx.restore()
}

// ── PNG ─────────────────────────────────────────────────────────────

export interface ExportPNGOptions {
  /** World units of empty space around the scene bounds. Keeps the
   *  outermost strokes from getting clipped at the canvas edge. */
  padding?: number
  /** Background fill. ``null`` / ``'transparent'`` leaves the canvas
   *  un-filled so the PNG has an alpha channel. */
  background?: string | null
  /** Rendering scale — 2 produces a retina-sharp export. */
  scale?: number
  /** Canvas factory, injectable for tests. Defaults to
   *  ``document.createElement('canvas')``. */
  createCanvas?: () => HTMLCanvasElement
}

const DEFAULT_PADDING = 24
const DEFAULT_BACKGROUND = '#ffffff'
const DEFAULT_SCALE = 2

/** Rasterise ``elements`` to a PNG blob. The returned promise resolves
 *  with ``null`` when the input was empty or the browser couldn't
 *  produce a blob (offscreen environments). Callers handle both. */
export async function exportToPNG(
  elements: readonly CollabElement[],
  options: ExportPNGOptions = {},
): Promise<Blob | null> {
  const bounds = computeBounds(elements)
  if (!bounds || bounds.width <= 0 || bounds.height <= 0) return null

  const padding = options.padding ?? DEFAULT_PADDING
  const background = options.background ?? DEFAULT_BACKGROUND
  const scale = options.scale ?? DEFAULT_SCALE

  const worldWidth = bounds.width + padding * 2
  const worldHeight = bounds.height + padding * 2

  const factory =
    options.createCanvas ??
    (() => document.createElement('canvas') as HTMLCanvasElement)
  const canvas = factory()
  canvas.width = Math.max(1, Math.ceil(worldWidth * scale))
  canvas.height = Math.max(1, Math.ceil(worldHeight * scale))

  const ctx = canvas.getContext('2d')
  if (!ctx) return null

  if (background !== null && background !== 'transparent') {
    ctx.fillStyle = background
    ctx.fillRect(0, 0, canvas.width, canvas.height)
  }

  paintElementsOnto(ctx, elements, {
    offsetX: bounds.x - padding,
    offsetY: bounds.y - padding,
    scale,
  })

  return new Promise((resolve) => {
    canvas.toBlob((blob) => resolve(blob), 'image/png')
  })
}

// ── Download helper ─────────────────────────────────────────────────

/** Trigger a browser download of ``blob`` as ``filename``. The demo
 *  uses this from its toolbar; production callers (a future export
 *  menu in ``useCollabRoom``) do the same. No-op in SSR. */
export function downloadBlob(blob: Blob, filename: string): void {
  if (typeof window === 'undefined') return
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  document.body.appendChild(a)
  a.click()
  a.remove()
  // Release on the next tick so the browser has definitely started
  // the download request. Delaying slightly is safer than immediate
  // revoke, which some browsers race against.
  setTimeout(() => URL.revokeObjectURL(url), 1000)
}
