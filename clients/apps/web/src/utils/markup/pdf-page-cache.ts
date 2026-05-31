/**
 * Module-level cache of rendered PDF pages keyed by ``(assetHash, page)``.
 *
 * Each entry is the offscreen canvas that pdfjs-dist drew the page
 * into. The painter (`shapes/pdf-underlay.ts`) blits from this canvas
 * onto the main scene canvas — no re-rasterisation per frame.
 *
 * Eviction: LRU bounded at 100 entries. PDFs are heavy; an
 * uncontrolled cache on a board with many pages would exhaust GPU
 * memory.
 *
 * Tied to the document lifetime (process-wide). Tests reset via
 * ``_resetPdfPageCache``.
 */

const MAX_ENTRIES = 100

export type PdfPageStatus = 'loading' | 'loaded' | 'error'

export interface PdfPageEntry {
  status: PdfPageStatus
  /** Populated when ``status === 'loaded'``. */
  canvas: HTMLCanvasElement | null
  /** Natural rendered dimensions, captured at load time. */
  width: number
  height: number
}

const cache = new Map<string, PdfPageEntry>()

export function pdfPageCacheKey(assetHash: string, page: number): string {
  return `${assetHash}:${page}`
}

export function getPdfPage(
  assetHash: string,
  page: number,
): PdfPageEntry | undefined {
  return cache.get(pdfPageCacheKey(assetHash, page))
}

export function setPdfPage(
  assetHash: string,
  page: number,
  entry: PdfPageEntry,
): void {
  const key = pdfPageCacheKey(assetHash, page)
  // Touch for LRU semantics: delete + re-set moves the key to the
  // end of the Map's insertion order.
  cache.delete(key)
  cache.set(key, entry)
  if (cache.size > MAX_ENTRIES) {
    // Evict the oldest (first-inserted) key.
    const oldest = cache.keys().next().value
    if (oldest !== undefined) cache.delete(oldest)
  }
}

/** Test-only reset. Cache state is process-wide; tests need a clean
 *  slate to avoid cross-test bleed. */
export function _resetPdfPageCache(): void {
  cache.clear()
}

/** Test-only size accessor. */
export function _pdfPageCacheSize(): number {
  return cache.size
}
