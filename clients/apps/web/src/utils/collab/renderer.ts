/**
 * Collab v2 renderer.
 *
 * Orchestrates two canvases, a Path2D cache, and a ``requestAnimation-
 * Frame``-batched repaint loop.
 *
 * Two-canvas design (§3.2 of the plan)
 * ------------------------------------
 * - **Static canvas:** paints every committed element. Repaints on
 *   ``store`` observe events and on ``setViewport``. Heavy-ish; we
 *   coalesce multiple dirty triggers into a single RAF.
 * - **Interactive canvas:** tool overlays (drag preview, selection
 *   rectangle, in-progress freehand, hover halos, remote cursors).
 *   Cheaper; repaints more often. In Phase 1b we only expose the
 *   hook — actual overlay drawing lands with the tool PRs.
 *
 * Path2D cache
 * ------------
 * Every element's shape is cached by ``id + version``. Repaints
 * iterate the store's ``list()``, reuse cached paths whose version
 * matches the current element, and rebuild on miss. The cache also
 * powers ``hitTest`` so we don't rebuild a Path2D per pointer-move.
 *
 * Coalescing
 * ----------
 * A flurry of ``observe`` events during a multi-element edit fires
 * one RAF per frame, not one per event. ``invalidate()`` just sets
 * a dirty flag; the RAF picks it up.
 */

import type * as Y from 'yjs'

import type { ElementStore } from './element-store'
import type { CollabElement } from './elements'
import { drawGrid } from './grid'
import { adapterFor } from './shapes'
import {
  applyViewportTransform,
  makeViewport,
  screenToWorld,
  type Viewport,
} from './viewport'

export interface RendererOptions {
  staticCanvas: HTMLCanvasElement
  interactiveCanvas: HTMLCanvasElement
  store: ElementStore
  viewport?: Viewport
  /** Optional background colour; defaults to paper-white matching the
   *  plan. Pass ``'transparent'`` to leave the canvas cleared. */
  background?: string
  /** Device pixel ratio. Provided for tests that want determinism. */
  dpr?: number
  /** Render a dotted grid overlay underneath every element. Default
   *  ``false`` — visible only when the user toggles via the command
   *  palette. */
  gridEnabled?: boolean
  /** World-units between grid lines. Default 20. */
  gridSize?: number
}

interface CacheEntry {
  version: number
  path: Path2D
}

export class Renderer {
  private readonly staticCanvas: HTMLCanvasElement
  private readonly interactiveCanvas: HTMLCanvasElement
  private readonly staticCtx: CanvasRenderingContext2D
  private readonly interactiveCtx: CanvasRenderingContext2D
  private readonly store: ElementStore
  private readonly background: string
  private readonly dpr: number

  private viewport: Viewport
  private gridEnabled: boolean
  private gridSize: number
  private readonly pathCache = new Map<string, CacheEntry>()
  private unobserve: (() => void) | null = null
  private rafHandle: number | null = null
  private dirty = true
  private destroyed = false
  private interactivePaintHook:
    | ((ctx: CanvasRenderingContext2D) => void)
    | null = null

  constructor(opts: RendererOptions) {
    this.staticCanvas = opts.staticCanvas
    this.interactiveCanvas = opts.interactiveCanvas
    this.store = opts.store
    this.background = opts.background ?? '#fafaf6'
    this.dpr =
      opts.dpr ??
      (typeof window !== 'undefined' ? window.devicePixelRatio || 1 : 1)
    this.viewport = opts.viewport ?? makeViewport()
    this.gridEnabled = opts.gridEnabled ?? false
    this.gridSize = opts.gridSize ?? 20

    const staticCtx = this.staticCanvas.getContext('2d')
    const interactiveCtx = this.interactiveCanvas.getContext('2d')
    if (!staticCtx || !interactiveCtx) {
      throw new Error('Renderer requires 2d canvases on both layers')
    }
    this.staticCtx = staticCtx
    this.interactiveCtx = interactiveCtx

    this.resizeCanvases()

    this.unobserve = this.store.observeDeep(this.onStoreEvents)
    this.scheduleRepaint()
  }

  /** Update the viewport and schedule a repaint. */
  setViewport(vp: Viewport): void {
    this.viewport = vp
    this.scheduleRepaint()
  }

  /** Toggle the dotted grid overlay. */
  setGridEnabled(enabled: boolean): void {
    if (this.gridEnabled === enabled) return
    this.gridEnabled = enabled
    this.scheduleRepaint()
  }

  isGridEnabled(): boolean {
    return this.gridEnabled
  }

  getGridSize(): number {
    return this.gridSize
  }

  /** Current viewport — callers should treat it as read-only. */
  getViewport(): Viewport {
    return this.viewport
  }

  /** Resize both canvases to the element's CSS box times ``dpr``. Call
   *  after any ResizeObserver or window-resize event. */
  resize(): void {
    this.resizeCanvases()
    this.scheduleRepaint()
  }

  /** Invalidate and repaint on the next RAF. Safe to call from many
   *  places — only one paint happens per frame. */
  invalidate(): void {
    this.scheduleRepaint()
  }

  /** Hook for drawing tool overlays onto the interactive canvas. The
   *  callback runs after every paint with a context that's already
   *  had the viewport transform applied and the canvas cleared. Pass
   *  ``null`` to remove the hook. */
  setInteractivePaint(
    fn: ((ctx: CanvasRenderingContext2D) => void) | null,
  ): void {
    this.interactivePaintHook = fn
    this.scheduleRepaint()
  }

  /** Return the topmost element whose Path2D contains the world-space
   *  point, or ``null``. Iterates element list in paint order and takes
   *  the last match (highest zIndex under the cursor). */
  hitTest(worldX: number, worldY: number): string | null {
    const elements = this.store.list()
    let found: string | null = null
    for (const el of elements) {
      const path = this.getCachedPath(el)
      if (!path) continue
      // Hit test in element-local space by inverting the world
      // transform: translate to (x, y), rotate by -angle around the
      // element centre.
      const cx = el.width / 2
      const cy = el.height / 2
      const dx = worldX - el.x - cx
      const dy = worldY - el.y - cy
      const cos = Math.cos(-el.angle)
      const sin = Math.sin(-el.angle)
      const localX = dx * cos - dy * sin + cx
      const localY = dx * sin + dy * cos + cy
      if (this.staticCtx.isPointInPath(path, localX, localY)) {
        found = el.id
      }
    }
    return found
  }

  /** Convert a screen-space (canvas-local, CSS pixels) point to world
   *  coords. Convenience wrapper for tools. */
  screenToWorld(screenX: number, screenY: number): { x: number; y: number } {
    return screenToWorld(this.viewport, screenX, screenY)
  }

  /** Tear down the store observer and cancel any pending RAF. */
  destroy(): void {
    if (this.destroyed) return
    this.destroyed = true
    this.unobserve?.()
    this.unobserve = null
    if (this.rafHandle != null) {
      cancelAnimationFrame(this.rafHandle)
      this.rafHandle = null
    }
    this.pathCache.clear()
  }

  // ── Internals ────────────────────────────────────────────────────

  private onStoreEvents = (
    events: Y.YEvent<Y.AbstractType<unknown>>[],
  ): void => {
    // Any element changed → invalidate its cache entry. We don't
    // know which keys on which ids from the event list without more
    // work; simplest correct approach is to let the cache rebuild
    // lazily on next paint by clearing stale entries.
    for (const evt of events) {
      // Root-level events carry the element id in their target path.
      const path = evt.path
      if (path.length > 0 && typeof path[0] === 'string') {
        this.pathCache.delete(path[0])
      } else {
        // Root-level add/remove — clear everything to be safe.
        this.pathCache.clear()
      }
    }
    this.scheduleRepaint()
  }

  private scheduleRepaint(): void {
    if (this.destroyed) return
    this.dirty = true
    if (this.rafHandle != null) return
    if (typeof requestAnimationFrame === 'undefined') {
      // Headless / test fallback — paint synchronously so tests can
      // assert without awaiting RAF timing.
      this.paint()
      return
    }
    this.rafHandle = requestAnimationFrame(() => {
      this.rafHandle = null
      if (this.dirty) this.paint()
    })
  }

  private paint(): void {
    if (this.destroyed) return
    this.dirty = false
    this.paintStatic()
    this.paintInteractive()
  }

  private paintStatic(): void {
    const ctx = this.staticCtx
    const rect = this.staticCanvas.getBoundingClientRect()
    ctx.setTransform(1, 0, 0, 1, 0, 0)
    if (this.background === 'transparent') {
      ctx.clearRect(0, 0, rect.width * this.dpr, rect.height * this.dpr)
    } else {
      ctx.fillStyle = this.background
      ctx.fillRect(0, 0, rect.width * this.dpr, rect.height * this.dpr)
    }
    // dpr scale; then viewport transform.
    ctx.setTransform(this.dpr, 0, 0, this.dpr, 0, 0)
    if (this.gridEnabled) {
      drawGrid(ctx, this.viewport, rect.width, rect.height, this.gridSize)
    }
    applyViewportTransform(ctx, this.viewport)
    // Re-apply dpr on top of the viewport transform.
    const vp = this.viewport
    ctx.setTransform(
      vp.scale * this.dpr,
      0,
      0,
      vp.scale * this.dpr,
      -vp.scrollX * vp.scale * this.dpr,
      -vp.scrollY * vp.scale * this.dpr,
    )

    for (const el of this.store.list()) {
      const adapter = adapterFor(el)
      if (!adapter) continue
      const path = this.getCachedPath(el, adapter.pathFor)
      if (!path) continue
      ctx.save()
      // World transform for this element: translate to (x, y) then
      // rotate around its centre.
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
  }

  private paintInteractive(): void {
    const ctx = this.interactiveCtx
    const rect = this.interactiveCanvas.getBoundingClientRect()
    ctx.setTransform(1, 0, 0, 1, 0, 0)
    ctx.clearRect(0, 0, rect.width * this.dpr, rect.height * this.dpr)
    if (!this.interactivePaintHook) return
    const vp = this.viewport
    ctx.setTransform(
      vp.scale * this.dpr,
      0,
      0,
      vp.scale * this.dpr,
      -vp.scrollX * vp.scale * this.dpr,
      -vp.scrollY * vp.scale * this.dpr,
    )
    this.interactivePaintHook(ctx)
  }

  private getCachedPath(
    el: CollabElement,
    fallback?: (el: CollabElement) => Path2D,
  ): Path2D | null {
    const cached = this.pathCache.get(el.id)
    if (cached && cached.version === el.version) return cached.path
    const build = fallback ?? adapterFor(el)?.pathFor
    if (!build) return null
    const path = build(el)
    this.pathCache.set(el.id, { version: el.version, path })
    return path
  }

  private resizeCanvases(): void {
    for (const canvas of [this.staticCanvas, this.interactiveCanvas]) {
      const rect = canvas.getBoundingClientRect()
      canvas.width = Math.max(1, Math.floor(rect.width * this.dpr))
      canvas.height = Math.max(1, Math.floor(rect.height * this.dpr))
    }
  }
}
