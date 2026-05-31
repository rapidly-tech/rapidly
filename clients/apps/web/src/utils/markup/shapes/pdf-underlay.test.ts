/**
 * Tests for the pdf-underlay shape adapter.
 *
 * Path geometry + placeholder semantics only. The async render loop
 * is mocked via the cache (set + assert) so the test stays
 * synchronous; the real pdfjs render is exercised via integration
 * tests when the backend asset endpoint is wired up.
 */

import { afterEach, beforeAll, describe, expect, it } from 'vitest'

// jsdom has no canvas backend and therefore no Path2D. Stub it so
// pathFor can instantiate without throwing. (Same pattern used by
// the existing shape tests; see shapes/text.test.ts.)
beforeAll(() => {
  if (typeof (globalThis as { Path2D?: unknown }).Path2D === 'undefined') {
    ;(globalThis as { Path2D: unknown }).Path2D = class {
      rect() {}
    }
  }
})

import type { PdfUnderlayElement } from '../elements'
import {
  _pdfPageCacheSize,
  _resetPdfPageCache,
  setPdfPage,
} from '../pdf-page-cache'
import { paintPdfUnderlay, pathFor } from './pdf-underlay'

afterEach(() => _resetPdfPageCache())

function makeElement(
  overrides: Partial<PdfUnderlayElement> = {},
): PdfUnderlayElement {
  return {
    id: 'pdf-1',
    type: 'pdf-underlay',
    x: 0,
    y: 0,
    width: 400,
    height: 565, // ~A4 portrait at scale
    angle: 0,
    zIndex: 0,
    groupIds: [],
    version: 1,
    locked: false,
    strokeColor: '#000',
    fillColor: 'transparent',
    strokeWidth: 1,
    opacity: 100,
    fillStyle: 'none',
    strokeStyle: 'solid',
    roughness: 0,
    seed: 1,
    assetHash: 'abc',
    page: 1,
    pageWidth: 595,
    pageHeight: 842,
    ...overrides,
  }
}

describe('pathFor', () => {
  it('returns a Path2D-like object for the element bounding box', () => {
    const path = pathFor(makeElement())
    expect(path).toBeDefined()
  })

  it('is shape-driven (element dimensions are the only inputs)', () => {
    // No throw on assetHash=undefined; pathFor only reads geometry.
    const path = pathFor(makeElement({ assetHash: undefined }))
    expect(path).toBeDefined()
  })
})

describe('paintPdfUnderlay placeholders', () => {
  // Tiny ctx-shaped stub. Only the methods the painter calls need to
  // be present; we record calls so tests can assert what was drawn.
  function makeStubCtx() {
    const calls: string[] = []
    const ctx = {
      save: () => calls.push('save'),
      restore: () => calls.push('restore'),
      fill: () => calls.push('fill'),
      stroke: () => calls.push('stroke'),
      drawImage: () => calls.push('drawImage'),
      fillText: (s: string) => calls.push(`fillText:${s}`),
      setLineDash: () => calls.push('setLineDash'),
      canvas: { dispatchEvent: () => true },
      fillStyle: '',
      strokeStyle: '',
      lineWidth: 0,
      globalAlpha: 1,
      font: '',
      textBaseline: '',
    } as unknown as CanvasRenderingContext2D
    return { ctx, calls }
  }

  it('paints a "no-asset" placeholder when assetHash is undefined', () => {
    const { ctx, calls } = makeStubCtx()
    paintPdfUnderlay(
      ctx,
      makeElement({ assetHash: undefined }),
      pathFor(makeElement()),
    )
    // Placeholder draws fill + stroke + label.
    expect(calls).toContain('fill')
    expect(calls).toContain('stroke')
    expect(
      calls.some(
        (c) => c.startsWith('fillText:') && c.includes('upload pending'),
      ),
    ).toBe(true)
    // No drawImage because there's no cached page.
    expect(calls).not.toContain('drawImage')
  })

  it('paints a "loading" placeholder + seeds the cache on first sight', () => {
    const { ctx, calls } = makeStubCtx()
    paintPdfUnderlay(ctx, makeElement(), pathFor(makeElement()))
    expect(calls).toContain('fill')
    expect(
      calls.some((c) => c.startsWith('fillText:') && c.includes('PDF page 1')),
    ).toBe(true)
    // The painter populates a 'loading' cache entry on first paint
    // so subsequent paints don't re-kick the render.
    expect(_pdfPageCacheSize()).toBe(1)
  })

  it('paints the cached page bitmap when status=loaded', () => {
    const { ctx, calls } = makeStubCtx()
    setPdfPage('abc', 1, {
      status: 'loaded',
      canvas: document.createElement('canvas'),
      width: 595,
      height: 842,
    })
    paintPdfUnderlay(ctx, makeElement(), pathFor(makeElement()))
    expect(calls).toContain('drawImage')
    // No placeholder calls when we have the bitmap.
    expect(calls.some((c) => c.startsWith('fillText:'))).toBe(false)
  })

  it('paints an "error" placeholder when status=error', () => {
    const { ctx, calls } = makeStubCtx()
    setPdfPage('abc', 1, { status: 'error', canvas: null, width: 0, height: 0 })
    paintPdfUnderlay(ctx, makeElement(), pathFor(makeElement()))
    expect(
      calls.some((c) => c.startsWith('fillText:') && c.includes('failed')),
    ).toBe(true)
    expect(calls).not.toContain('drawImage')
  })
})
