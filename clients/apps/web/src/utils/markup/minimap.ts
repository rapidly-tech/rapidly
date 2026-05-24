/**
 * Minimap projection — pure layout helpers for the corner-overview
 * widget. Given the world-space scene bounds + viewport + minimap
 * canvas size, returns the world→minimap transform plus the
 * viewport-rect to draw on top of the scene preview.
 *
 * The visible UI lives in ``components/Collab/Whiteboard/Minimap.tsx``;
 * everything in this module is renderer-agnostic so the click-to-pan
 * + keyboard-pan paths can compute coordinates without touching DOM.
 */

import type { CollabElement } from './elements'
import type { Viewport } from './viewport'

export interface MinimapBounds {
  /** World-space bounding box of every element on the scene. Empty
   *  scenes get a synthetic ``0,0,1,1`` so callers don't divide by
   *  zero. */
  minX: number
  minY: number
  maxX: number
  maxY: number
}

export interface MinimapProjection {
  bounds: MinimapBounds
  /** World units per minimap pixel. Multiply a world delta by
   *  ``1/scale`` to get the equivalent minimap delta. */
  scale: number
  /** Minimap-space top-left of the projected world bounds. Always
   *  >= 0; used to centre the projection inside the minimap canvas
   *  when the world aspect ratio doesn't match. */
  offsetX: number
  offsetY: number
}

export interface MinimapRect {
  x: number
  y: number
  width: number
  height: number
}

/** Compute the world-space bounds of every element. Pure, returns
 *  a synthetic 1×1 rect for empty scenes so callers can render a
 *  blank minimap without special-casing. */
export function computeSceneBounds(elements: CollabElement[]): MinimapBounds {
  if (elements.length === 0) {
    return { minX: 0, minY: 0, maxX: 1, maxY: 1 }
  }
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
  return { minX, minY, maxX, maxY }
}

/** Build the world→minimap transform that fits ``bounds`` inside a
 *  ``mapWidth × mapHeight`` minimap canvas while preserving aspect
 *  ratio (letterboxes the shorter axis). */
export function projectToMinimap(
  bounds: MinimapBounds,
  mapWidth: number,
  mapHeight: number,
  padding = 4,
): MinimapProjection {
  const w = Math.max(1, bounds.maxX - bounds.minX)
  const h = Math.max(1, bounds.maxY - bounds.minY)
  const usableW = Math.max(1, mapWidth - padding * 2)
  const usableH = Math.max(1, mapHeight - padding * 2)
  // Scale = world units per minimap pixel. Take the larger so the
  // whole scene fits; the smaller axis gets letterboxed.
  const scale = Math.max(w / usableW, h / usableH)
  const projectedW = w / scale
  const projectedH = h / scale
  const offsetX = padding + (usableW - projectedW) / 2
  const offsetY = padding + (usableH - projectedH) / 2
  return { bounds, scale, offsetX, offsetY }
}

/** Project a world-space rect (e.g. an element's bounding box) into
 *  minimap-space pixel coords. */
export function projectRect(
  rect: MinimapRect,
  proj: MinimapProjection,
): MinimapRect {
  return {
    x: proj.offsetX + (rect.x - proj.bounds.minX) / proj.scale,
    y: proj.offsetY + (rect.y - proj.bounds.minY) / proj.scale,
    width: rect.width / proj.scale,
    height: rect.height / proj.scale,
  }
}

/** Project the current viewport rectangle onto the minimap. The
 *  viewport sees ``canvasWidth/scale × canvasHeight/scale`` world
 *  units starting at ``scrollX, scrollY``. */
export function projectViewportRect(
  viewport: Viewport,
  canvasWidth: number,
  canvasHeight: number,
  proj: MinimapProjection,
): MinimapRect {
  return projectRect(
    {
      x: viewport.scrollX,
      y: viewport.scrollY,
      width: canvasWidth / viewport.scale,
      height: canvasHeight / viewport.scale,
    },
    proj,
  )
}

/** Inverse of ``projectRect``'s position component — pick a point in
 *  minimap-space pixels and return its world-space equivalent. Used
 *  by click-to-pan: the user clicks a spot on the minimap and we
 *  re-centre the viewport on the corresponding world point. */
export function minimapPointToWorld(
  mx: number,
  my: number,
  proj: MinimapProjection,
): { x: number; y: number } {
  return {
    x: proj.bounds.minX + (mx - proj.offsetX) * proj.scale,
    y: proj.bounds.minY + (my - proj.offsetY) * proj.scale,
  }
}

/** Compute the viewport that would centre on the given world point
 *  while preserving its current zoom. Pure — caller decides how to
 *  apply it. */
export function centreViewportOn(
  viewport: Viewport,
  worldX: number,
  worldY: number,
  canvasWidth: number,
  canvasHeight: number,
): Viewport {
  return {
    scale: viewport.scale,
    scrollX: worldX - canvasWidth / viewport.scale / 2,
    scrollY: worldY - canvasHeight / viewport.scale / 2,
  }
}
