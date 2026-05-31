/**
 * pdfjs-dist loader for the Markup chamber's PDF underlay element.
 *
 * Renders a single page from a PDF URL into an offscreen canvas and
 * caches the result via ``pdf-page-cache``. The painter
 * (`shapes/pdf-underlay.ts`) is synchronous; it calls into this
 * loader to kick off a render the first time it sees a fresh
 * ``(assetHash, page)`` pair, and reads the cache on subsequent
 * paints.
 *
 * pdfjs-dist ships a separate worker. We point ``GlobalWorkerOptions``
 * at the vendored worker bundle so the request stays same-origin —
 * the production CSP's ``worker-src`` doesn't allow cross-origin
 * worker fetches.
 *
 * The loader is intentionally tolerant: any failure (404, parse
 * error, missing worker, abort) flips the cache entry to ``error``
 * and the painter falls back to a placeholder. No exception
 * propagates into the render loop.
 *
 * Backend asset URL: ``/api/markup/assets/{assetHash}``. This
 * endpoint lands in a follow-up PR that wires application/pdf
 * support into the markup asset store; until then the fetch will
 * 404 and the painter shows the placeholder. The painter's shape is
 * complete now so no painter changes are needed when the backend
 * arrives.
 */

import { getPdfPage, pdfPageCacheKey, setPdfPage } from './pdf-page-cache'

/** Resolves the URL we fetch PDF bytes from. Centralised so a
 *  followup that wires the backend can point at whatever path the
 *  asset store actually exposes. */
export function pdfAssetUrl(assetHash: string): string {
  return `/api/markup/assets/${encodeURIComponent(assetHash)}`
}

/** Per-document handle returned by pdfjs. Cached so we don't re-parse
 *  the document for each page request. */
const documentCache = new Map<string, Promise<unknown>>()

/** Per-render in-flight promise so concurrent paints of the same
 *  (asset, page) collapse to one render. */
const renderInFlight = new Set<string>()

/** Kick off a render of (assetHash, page). Returns immediately. On
 *  success or failure, the cache entry is updated; the renderer
 *  receives an event so it can repaint. Idempotent — calling twice
 *  for the same key while a render is in-flight is a no-op. */
export function ensurePdfPageRendered(
  assetHash: string,
  page: number,
  onInvalidate: () => void,
): void {
  const key = pdfPageCacheKey(assetHash, page)
  if (renderInFlight.has(key)) return
  const hit = getPdfPage(assetHash, page)
  if (hit && hit.status !== 'loading') return

  renderInFlight.add(key)
  setPdfPage(assetHash, page, {
    status: 'loading',
    canvas: null,
    width: 0,
    height: 0,
  })

  void renderPage(assetHash, page)
    .then((entry) => {
      setPdfPage(assetHash, page, entry)
      onInvalidate()
    })
    .catch(() => {
      setPdfPage(assetHash, page, {
        status: 'error',
        canvas: null,
        width: 0,
        height: 0,
      })
      onInvalidate()
    })
    .finally(() => {
      renderInFlight.delete(key)
    })
}

async function renderPage(
  assetHash: string,
  page: number,
): Promise<{
  status: 'loaded'
  canvas: HTMLCanvasElement
  width: number
  height: number
}> {
  const pdfjs = await import('pdfjs-dist')
  // Vendored worker. The CSP forbids cross-origin worker-src, so we
  // bundle pdfjs's worker alongside the app and point at it relative
  // to the document origin.
  if (!pdfjs.GlobalWorkerOptions.workerSrc) {
    // The new-URL-with-import.meta.url pattern lets the bundler
    // (Next.js + Turbopack) emit the worker as a same-origin asset.
    pdfjs.GlobalWorkerOptions.workerSrc = new URL(
      'pdfjs-dist/build/pdf.worker.min.mjs',
      import.meta.url,
    ).toString()
  }

  const url = pdfAssetUrl(assetHash)
  let pdfDocPromise = documentCache.get(assetHash) as
    | Promise<{ getPage: (n: number) => Promise<unknown> }>
    | undefined
  if (!pdfDocPromise) {
    pdfDocPromise = pdfjs
      .getDocument({ url })
      .promise.then(
        (doc) => doc as { getPage: (n: number) => Promise<unknown> },
      )
    documentCache.set(assetHash, pdfDocPromise)
  }
  const pdfDoc = await pdfDocPromise
  const pdfPage = (await pdfDoc.getPage(page)) as {
    getViewport: (args: { scale: number }) => { width: number; height: number }
    render: (args: {
      canvasContext: CanvasRenderingContext2D
      viewport: { width: number; height: number }
    }) => { promise: Promise<void> }
  }
  const viewport = pdfPage.getViewport({ scale: 1 })
  const canvas = document.createElement('canvas')
  canvas.width = Math.ceil(viewport.width)
  canvas.height = Math.ceil(viewport.height)
  const ctx = canvas.getContext('2d')
  if (!ctx) throw new Error('2d context unavailable')
  await pdfPage.render({ canvasContext: ctx, viewport }).promise

  return {
    status: 'loaded',
    canvas,
    width: viewport.width,
    height: viewport.height,
  }
}

/** Test-only reset of the document + in-flight caches. */
export function _resetPdfLoader(): void {
  documentCache.clear()
  renderInFlight.clear()
}
