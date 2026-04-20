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
import { pathFor as arrowPath, paintArrow } from './arrow'
import { pathFor as diamondPath, paintDiamond } from './diamond'
import { pathFor as ellipsePath, paintEllipse } from './ellipse'
import { pathFor as freeDrawPath, paintFreeDraw } from './freedraw'
import { pathFor as linePath, paintLine } from './line'
import { paintRect, pathFor as rectPath } from './rect'
import { paintText, pathFor as textPath } from './text'

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
  diamond: {
    pathFor: (el) => diamondPath(el as Parameters<typeof diamondPath>[0]),
    paint: (ctx, el, path) =>
      paintDiamond(ctx, el as Parameters<typeof paintDiamond>[1], path),
  },
  line: {
    pathFor: (el) => linePath(el as Parameters<typeof linePath>[0]),
    paint: (ctx, el, path) =>
      paintLine(ctx, el as Parameters<typeof paintLine>[1], path),
  },
  arrow: {
    pathFor: (el) => arrowPath(el as Parameters<typeof arrowPath>[0]),
    paint: (ctx, el, path) =>
      paintArrow(ctx, el as Parameters<typeof paintArrow>[1], path),
  },
  freedraw: {
    pathFor: (el) => freeDrawPath(el as Parameters<typeof freeDrawPath>[0]),
    paint: (ctx, el, path) =>
      paintFreeDraw(ctx, el as Parameters<typeof paintFreeDraw>[1], path),
  },
  text: {
    pathFor: (el) => textPath(el as Parameters<typeof textPath>[0]),
    paint: (ctx, el, path) =>
      paintText(ctx, el as Parameters<typeof paintText>[1], path),
  },
  // Remaining types (sticky, image, frame, embed) land later.
}

export function adapterFor(el: CollabElement): ShapeAdapter | null {
  return REGISTRY[el.type] ?? null
}

export {
  arrowPath,
  diamondPath,
  ellipsePath,
  freeDrawPath,
  linePath,
  paintArrow,
  paintDiamond,
  paintEllipse,
  paintFreeDraw,
  paintLine,
  paintRect,
  paintText,
  rectPath,
  textPath,
}
