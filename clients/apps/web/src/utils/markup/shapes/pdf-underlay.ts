/**
 * PDF-underlay painter for the Markup chamber renderer.
 *
 * The element's bounding box defines where the page draws on the
 * scene. The painter looks up the rasterised page in
 * ``pdf-page-cache``; on miss it kicks off an async render via
 * ``pdf-loader.ensurePdfPageRendered`` and draws a placeholder.
 * On the next repaint the cache hit blits the canvas in.
 *
 * Errors degrade to a placeholder — never an exception out of the
 * paint loop.
 */

import type { PdfUnderlayElement } from '../elements'
import { ensurePdfPageRendered } from '../pdf-loader'
import { getPdfPage } from '../pdf-page-cache'

/** Hit + paint Path2D: a plain axis-aligned rect in element-local
 *  coordinates. */
export function pathFor(el: PdfUnderlayElement): Path2D {
  const path = new Path2D()
  path.rect(0, 0, el.width, el.height)
  return path
}

export function paintPdfUnderlay(
  ctx: CanvasRenderingContext2D,
  el: PdfUnderlayElement,
  path: Path2D,
): void {
  if (!el.assetHash) {
    paintPlaceholder(ctx, el, path, 'no-asset')
    return
  }

  const entry = getPdfPage(el.assetHash, el.page)
  if (!entry || entry.status === 'loading') {
    if (entry === undefined) {
      // First sight — kick off the async render. Subsequent paints
      // will see the cache entry transition through 'loading' →
      // 'loaded' / 'error' and react accordingly.
      ensurePdfPageRendered(el.assetHash, el.page, () => {
        ctx.canvas.dispatchEvent(
          new CustomEvent('rapidly-markup-pdf-page-loaded', { bubbles: true }),
        )
      })
    }
    paintPlaceholder(ctx, el, path, 'loading')
    return
  }
  if (entry.status === 'error' || !entry.canvas) {
    paintPlaceholder(ctx, el, path, 'error')
    return
  }

  ctx.save()
  ctx.globalAlpha = (el.opacity ?? 100) / 100
  // Draw the cached page bitmap into the element's on-canvas
  // footprint. Source rect = full rendered page; dest rect = the
  // element's bounding box.
  ctx.drawImage(entry.canvas, 0, 0, el.width, el.height)
  ctx.restore()
}

function paintPlaceholder(
  ctx: CanvasRenderingContext2D,
  el: PdfUnderlayElement,
  path: Path2D,
  reason: 'loading' | 'error' | 'no-asset',
): void {
  ctx.save()
  ctx.fillStyle =
    reason === 'error'
      ? 'rgba(254, 226, 226, 0.6)' // red-100/60
      : 'rgba(241, 245, 249, 0.6)' // slate-100/60
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
  // Label so the slot reads as a PDF page during the loading state
  // rather than as a generic rectangle.
  const label =
    reason === 'no-asset'
      ? `PDF page ${el.page} (upload pending)`
      : reason === 'error'
        ? `PDF page ${el.page} (failed to load)`
        : `PDF page ${el.page}`
  ctx.fillStyle = reason === 'error' ? '#7f1d1d' : '#475569'
  ctx.font =
    '12px ui-sans-serif, system-ui, -apple-system, "Segoe UI", Roboto, sans-serif'
  ctx.textBaseline = 'top'
  ctx.fillText(label, 8, 8)
  ctx.restore()
}
