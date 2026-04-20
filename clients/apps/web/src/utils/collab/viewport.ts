/**
 * Viewport math for the Collab v2 renderer.
 *
 * A ``Viewport`` describes how to project the whiteboard's world
 * coordinate space onto the canvas. Elements always store world
 * coordinates; the renderer multiplies by the viewport's ``scale`` and
 * subtracts ``scroll`` to get canvas pixels.
 *
 * Kept as plain data + pure functions so tools, hit-testers, and the
 * renderer share one source of truth. Anything that needs to convert
 * between screen and world coords goes through the helpers in this
 * module.
 */

export interface Viewport {
  /** Zoom factor. 1 = 1 world unit → 1 canvas pixel. */
  scale: number
  /** World coordinate shown at the canvas's top-left corner. */
  scrollX: number
  scrollY: number
}

/** Minimum and maximum zoom — matches the plan's 10%–3000% window.
 *  Clamping happens at callers so we don't silently swallow invalid
 *  input; these are the canonical bounds. */
export const MIN_SCALE = 0.1
export const MAX_SCALE = 30

export function makeViewport(init?: Partial<Viewport>): Viewport {
  return {
    scale: init?.scale ?? 1,
    scrollX: init?.scrollX ?? 0,
    scrollY: init?.scrollY ?? 0,
  }
}

/** Clamp a scale into the allowed zoom range. */
export function clampScale(scale: number): number {
  if (!Number.isFinite(scale)) return 1
  return Math.max(MIN_SCALE, Math.min(MAX_SCALE, scale))
}

/** Convert a screen-space (canvas-local) point to world coords. */
export function screenToWorld(
  vp: Viewport,
  screenX: number,
  screenY: number,
): { x: number; y: number } {
  return {
    x: vp.scrollX + screenX / vp.scale,
    y: vp.scrollY + screenY / vp.scale,
  }
}

/** Convert a world point to screen-space (canvas-local) pixels. */
export function worldToScreen(
  vp: Viewport,
  worldX: number,
  worldY: number,
): { x: number; y: number } {
  return {
    x: (worldX - vp.scrollX) * vp.scale,
    y: (worldY - vp.scrollY) * vp.scale,
  }
}

/** Zoom the viewport toward a screen-space anchor so the world point
 *  under the cursor stays fixed. The standard "zoom at cursor" pattern.
 *  Returns a new viewport — the original is not mutated. */
export function zoomAt(
  vp: Viewport,
  anchorScreenX: number,
  anchorScreenY: number,
  nextScale: number,
): Viewport {
  const clamped = clampScale(nextScale)
  const { x: worldX, y: worldY } = screenToWorld(
    vp,
    anchorScreenX,
    anchorScreenY,
  )
  return {
    scale: clamped,
    scrollX: worldX - anchorScreenX / clamped,
    scrollY: worldY - anchorScreenY / clamped,
  }
}

/** Pan the viewport by a delta in screen pixels (negative of drag). */
export function panByScreen(
  vp: Viewport,
  deltaScreenX: number,
  deltaScreenY: number,
): Viewport {
  return {
    ...vp,
    scrollX: vp.scrollX - deltaScreenX / vp.scale,
    scrollY: vp.scrollY - deltaScreenY / vp.scale,
  }
}

/** World-space rectangle that's currently visible. Used by the
 *  renderer to skip elements outside the view — Phase 1 paints every
 *  element anyway (perf POC shows it's fine), but the cull box is
 *  ready for Phase 2 when we add dirty-rect invalidation. */
export function visibleBounds(
  vp: Viewport,
  canvasWidth: number,
  canvasHeight: number,
): { x: number; y: number; width: number; height: number } {
  return {
    x: vp.scrollX,
    y: vp.scrollY,
    width: canvasWidth / vp.scale,
    height: canvasHeight / vp.scale,
  }
}

/** Apply the viewport transform to a 2D canvas context so subsequent
 *  draw calls can use world coordinates directly. Caller is responsible
 *  for ``ctx.setTransform(1,0,0,1,0,0)`` before the next clear. */
export function applyViewportTransform(
  ctx: CanvasRenderingContext2D,
  vp: Viewport,
): void {
  ctx.setTransform(
    vp.scale,
    0,
    0,
    vp.scale,
    -vp.scrollX * vp.scale,
    -vp.scrollY * vp.scale,
  )
}
