/**
 * Image painter for the Collab v2 renderer.
 *
 * Image elements store a base64 data URL thumbnail inline on the Yjs
 * doc (``ImageElement.thumbnailDataUrl``). The painter decodes each
 * unique data URL once via a module-level cache so redraws are cheap
 * and two elements sharing the same thumbnail (e.g. a duplicated
 * element) don't each re-decode.
 *
 * While an image is still loading we paint a neutral placeholder rect
 * in the element's fill colour so the scene isn't jarringly empty
 * during decode. On decode error we keep the placeholder — no
 * exception, no black box — so a corrupt or broken peer-supplied
 * image degrades to a benign visual rather than a render crash.
 */

import type { ImageElement } from '../elements'

/** Cache of decoded HTMLImageElements, keyed by their data URL. Image
 *  decoding is async; the cache entry holds the image *and* a status
 *  flag so pathFor / paint can skip the decode call-sites when we
 *  already know the result. */
const imageCache = new Map<
  string,
  { status: 'loading' | 'loaded' | 'error'; image: HTMLImageElement }
>()

/** The image element's hit + paint Path2D: a plain axis-aligned rect
 *  in element-local coordinates. The decoded image (if any) draws
 *  inside this rect; hit-testing falls back to the rect silhouette so
 *  clicking anywhere on the image bounding box selects it. */
export function pathFor(el: ImageElement): Path2D {
  const path = new Path2D()
  path.rect(0, 0, el.width, el.height)
  return path
}

export function paintImage(
  ctx: CanvasRenderingContext2D,
  el: ImageElement,
  path: Path2D,
): void {
  const cached = ensureCached(el.thumbnailDataUrl, () => ctx.canvas)
  if (cached.status === 'loaded') {
    ctx.save()
    ctx.globalAlpha = (el.opacity ?? 100) / 100
    ctx.drawImage(cached.image, 0, 0, el.width, el.height)
    ctx.restore()
  } else {
    // Placeholder — filled rect + subtle outline. Uses the element's
    // fill if set, otherwise a neutral tone so broken images still
    // read as a block of content.
    ctx.save()
    ctx.fillStyle =
      el.fillColor && el.fillColor !== 'transparent'
        ? el.fillColor
        : 'rgba(148, 163, 184, 0.35)' // slate-400/35
    ctx.fill(path)
    ctx.strokeStyle = cached.status === 'error' ? '#e03131' : '#94a3b8'
    ctx.lineWidth = 1
    ctx.stroke(path)
    ctx.restore()
  }
}

/** Look up a data URL in the cache, kicking off a decode on first
 *  sight. ``invalidate`` is called on load so the renderer can repaint
 *  once the image is actually available. */
function ensureCached(
  dataUrl: string,
  invalidateFn: () => HTMLCanvasElement | null,
): { status: 'loading' | 'loaded' | 'error'; image: HTMLImageElement } {
  const hit = imageCache.get(dataUrl)
  if (hit) return hit

  const image = new Image()
  const entry = { status: 'loading' as 'loading' | 'loaded' | 'error', image }
  imageCache.set(dataUrl, entry)

  image.onload = () => {
    entry.status = 'loaded'
    // Nudge the renderer by dispatching a repaint — canvas is mounted
    // when we painted the placeholder, so the event handler runs in
    // the same document.
    const canvas = invalidateFn()
    if (canvas) {
      canvas.dispatchEvent(
        new CustomEvent('rapidly-collab-image-loaded', { bubbles: true }),
      )
    }
  }
  image.onerror = () => {
    entry.status = 'error'
  }
  image.src = dataUrl

  return entry
}

/** Test-only reset. Decode state is process-wide; tests need a clean
 *  slate to avoid cross-test bleed. */
export function _resetImageCache(): void {
  imageCache.clear()
}
