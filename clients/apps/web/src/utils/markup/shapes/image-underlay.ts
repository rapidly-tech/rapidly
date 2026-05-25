/**
 * Image-underlay painter for the Markup chamber renderer.
 *
 * Distinct from ``image`` on purpose — see ``ImageUnderlayElement``
 * in ../elements.ts for the rationale. The painter is intentionally
 * simpler than ``shapes/image.ts``: no crop window, no thumbnail
 * fallback, no opacity-from-binding bookkeeping. An underlay is just
 * a locked rectangular bitmap that sits beneath every other element.
 *
 * Asset URL: ``/api/markup/assets/{assetHash}``. Same endpoint the
 * PDF underlay loader points at (M2.1). Until the backend wires
 * ``application/pdf`` and image mime-types through that path, the
 * fetch returns 404 and the painter shows a placeholder; no painter
 * changes required when the backend arrives.
 */

import type { ImageUnderlayElement } from '../elements'

type CacheEntry = {
  status: 'loading' | 'loaded' | 'error'
  image: HTMLImageElement
}

const imageCache = new Map<string, CacheEntry>()

/** Hit + paint Path2D: a plain axis-aligned rect in element-local
 *  coordinates. Underlays don't carry their own special-hit geometry;
 *  if a user holds Alt to bypass the ``locked`` flag, the selection
 *  hit-test will land on this rect like any other element. */
export function pathFor(el: ImageUnderlayElement): Path2D {
  const path = new Path2D()
  path.rect(0, 0, el.width, el.height)
  return path
}

export function paintImageUnderlay(
  ctx: CanvasRenderingContext2D,
  el: ImageUnderlayElement,
  path: Path2D,
): void {
  if (!el.assetHash) {
    paintPlaceholder(ctx, path, 'no-asset')
    return
  }
  const entry = ensureCached(el.assetHash, () => ctx.canvas)
  if (entry.status === 'loaded') {
    ctx.save()
    ctx.globalAlpha = (el.opacity ?? 100) / 100
    ctx.drawImage(entry.image, 0, 0, el.width, el.height)
    ctx.restore()
    return
  }
  paintPlaceholder(ctx, path, entry.status)
}

function paintPlaceholder(
  ctx: CanvasRenderingContext2D,
  path: Path2D,
  reason: 'loading' | 'error' | 'no-asset',
): void {
  ctx.save()
  ctx.fillStyle =
    reason === 'error'
      ? 'rgba(254, 226, 226, 0.5)' // red-100/50
      : 'rgba(241, 245, 249, 0.5)' // slate-100/50
  ctx.fill(path)
  ctx.strokeStyle =
    reason === 'error'
      ? '#dc2626'
      : reason === 'loading'
        ? '#94a3b8'
        : '#cbd5e1'
  ctx.lineWidth = 1
  ctx.setLineDash(reason === 'loading' ? [4, 4] : [])
  ctx.stroke(path)
  ctx.restore()
}

/** First-sight load: fetches the asset URL and decodes into an
 *  HTMLImageElement, caching the result. On load / error, invalidates
 *  the renderer so the next paint either blits the decoded bitmap or
 *  paints the error placeholder. */
function ensureCached(
  assetHash: string,
  invalidateFn: () => HTMLCanvasElement | null,
): CacheEntry {
  const hit = imageCache.get(assetHash)
  if (hit) return hit

  const image = new Image()
  const entry: CacheEntry = { status: 'loading', image }
  imageCache.set(assetHash, entry)

  image.onload = () => {
    entry.status = 'loaded'
    const canvas = invalidateFn()
    if (canvas) {
      canvas.dispatchEvent(
        new CustomEvent('rapidly-markup-image-underlay-loaded', {
          bubbles: true,
        }),
      )
    }
  }
  image.onerror = () => {
    entry.status = 'error'
    const canvas = invalidateFn()
    if (canvas) {
      canvas.dispatchEvent(
        new CustomEvent('rapidly-markup-image-underlay-loaded', {
          bubbles: true,
        }),
      )
    }
  }
  image.src = `/api/markup/assets/${encodeURIComponent(assetHash)}`

  return entry
}

/** Test-only reset of the decode cache. */
export function _resetImageUnderlayCache(): void {
  imageCache.clear()
}
