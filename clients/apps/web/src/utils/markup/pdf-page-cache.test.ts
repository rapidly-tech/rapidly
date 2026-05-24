/**
 * Tests for the PDF page cache. Pure unit-level — no DOM, no
 * canvases, no pdfjs.
 */

import { afterEach, describe, expect, it } from 'vitest'

import {
  _pdfPageCacheSize,
  _resetPdfPageCache,
  getPdfPage,
  pdfPageCacheKey,
  setPdfPage,
  type PdfPageEntry,
} from './pdf-page-cache'

afterEach(() => _resetPdfPageCache())

function fakeEntry(): PdfPageEntry {
  // The canvas field is allowed to be null for 'loading' / 'error';
  // tests don't need a real HTMLCanvasElement.
  return { status: 'loaded', canvas: null, width: 595, height: 842 }
}

describe('pdfPageCacheKey', () => {
  it('joins assetHash and page with a colon', () => {
    expect(pdfPageCacheKey('abc', 3)).toBe('abc:3')
  })

  it('distinguishes pages within the same asset', () => {
    expect(pdfPageCacheKey('abc', 1)).not.toBe(pdfPageCacheKey('abc', 2))
  })

  it('distinguishes assets at the same page', () => {
    expect(pdfPageCacheKey('a', 1)).not.toBe(pdfPageCacheKey('b', 1))
  })
})

describe('get/set', () => {
  it('returns undefined for a missing key', () => {
    expect(getPdfPage('missing', 1)).toBeUndefined()
  })

  it('round-trips a stored entry', () => {
    const e = fakeEntry()
    setPdfPage('abc', 1, e)
    expect(getPdfPage('abc', 1)).toBe(e)
  })

  it('overwrites a previous entry for the same key', () => {
    const e1 = fakeEntry()
    const e2 = { ...fakeEntry(), width: 1000 }
    setPdfPage('abc', 1, e1)
    setPdfPage('abc', 1, e2)
    expect(getPdfPage('abc', 1)).toBe(e2)
  })
})

describe('LRU eviction', () => {
  it('evicts the oldest entry once the cap is exceeded', () => {
    // The cap is 100; fill to 100, then add one more and observe
    // that the first key is gone.
    for (let i = 0; i < 100; i++) {
      setPdfPage('asset', i, fakeEntry())
    }
    expect(_pdfPageCacheSize()).toBe(100)
    expect(getPdfPage('asset', 0)).toBeDefined()

    setPdfPage('asset', 100, fakeEntry())
    expect(_pdfPageCacheSize()).toBe(100)
    // The first-inserted key was evicted; the newest is present.
    expect(getPdfPage('asset', 0)).toBeUndefined()
    expect(getPdfPage('asset', 100)).toBeDefined()
  })

  it('treats a re-set as a touch (moves the key to the back of LRU)', () => {
    // Insert 100 entries, then re-set key 0 (touch it), then push
    // one more. The touched key should survive; the next-oldest
    // (key 1) should evict.
    for (let i = 0; i < 100; i++) {
      setPdfPage('asset', i, fakeEntry())
    }
    setPdfPage('asset', 0, fakeEntry()) // touch
    setPdfPage('asset', 100, fakeEntry()) // push
    expect(getPdfPage('asset', 0)).toBeDefined() // survived
    expect(getPdfPage('asset', 1)).toBeUndefined() // evicted
    expect(getPdfPage('asset', 100)).toBeDefined()
  })
})
