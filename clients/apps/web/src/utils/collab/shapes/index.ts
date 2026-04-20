/**
 * Shape registry for the Collab v2 renderer.
 *
 * Every element type has:
 *  - ``pathFor(el)`` — element-local Path2D used for both paint and
 *    hit-testing. Cached per (elementId, version) by the renderer.
 *  - ``paint(ctx, el, path)`` — draw onto a context that's already
 *    positioned + rotated at the element's world-space origin.
 *
 * Lookup is by ``element.type`` so the renderer doesn't branch on
 * discriminants at every paint. Unknown types are skipped rather than
 * throwing: a future peer version may ship an element type we don't
 * know, and dropping it is better than crashing the render loop.
 */

import type { CollabElement, ElementType } from '../elements'
import { pathFor as ellipsePath, paintEllipse } from './ellipse'
import { paintRect, pathFor as rectPath } from './rect'

type PaintFn = (
  ctx: CanvasRenderingContext2D,
  el: CollabElement,
  path: Path2D,
) => void

type PathFn = (el: CollabElement) => Path2D

interface ShapeAdapter {
  pathFor: PathFn
  paint: PaintFn
}

const REGISTRY: Partial<Record<ElementType, ShapeAdapter>> = {
  rect: {
    pathFor: (el) => rectPath(el as Parameters<typeof rectPath>[0]),
    paint: (ctx, el, path) =>
      paintRect(ctx, el as Parameters<typeof paintRect>[1], path),
  },
  ellipse: {
    pathFor: (el) => ellipsePath(el as Parameters<typeof ellipsePath>[0]),
    paint: (ctx, el, path) =>
      paintEllipse(ctx, el as Parameters<typeof paintEllipse>[1], path),
  },
  // Remaining element types land in later phases. Their absence here
  // is intentional — the renderer skips them so nothing crashes in the
  // meantime.
}

/** Look up the shape adapter for a given element. Returns ``null``
 *  when no adapter is registered (unknown element type, or a type we
 *  haven't implemented yet). Callers should skip rather than throw. */
export function adapterFor(el: CollabElement): ShapeAdapter | null {
  return REGISTRY[el.type] ?? null
}

export { ellipsePath, paintEllipse, paintRect, rectPath }
