import { describe, expect, it } from 'vitest'

import { getFileName } from './fs'
import type { UploadedFile } from './types'

/** Build a lightweight stand-in for File so tests don't need to
 *  construct real browser File objects (which jsdom supports, but we
 *  only exercise ``entryFullPath`` + ``name`` here). WeakMap caching
 *  requires a real object identity; a fresh object per test is enough. */
function makeFile(name: string, entryFullPath?: string): UploadedFile {
  return { name, entryFullPath } as unknown as UploadedFile
}

describe('getFileName', () => {
  it('returns a plain name when no entryFullPath is set', () => {
    expect(getFileName(makeFile('report.pdf'))).toBe('report.pdf')
  })

  it('strips the leading slash from entryFullPath', () => {
    // webkitGetAsEntry gives paths like "/folder/file.txt"; downstream
    // Zod validation rejects the absolute form, so the uploader must
    // normalise.
    expect(getFileName(makeFile('file.txt', '/folder/file.txt'))).toBe(
      'folder/file.txt',
    )
  })

  it('leaves a relative entryFullPath alone', () => {
    expect(getFileName(makeFile('file.txt', 'folder/file.txt'))).toBe(
      'folder/file.txt',
    )
  })

  it('prefers entryFullPath over name when both are present', () => {
    expect(getFileName(makeFile('file.txt', '/folder/other.txt'))).toBe(
      'folder/other.txt',
    )
  })

  it('sanitises the name the same way the downloader Zod schema does', () => {
    // Windows-reserved device name gets prefixed with underscore so the
    // uploader / downloader agree on the final filename.
    expect(getFileName(makeFile('CON.txt'))).toBe('_CON.txt')
    // Windows-unsafe character becomes underscore.
    expect(getFileName(makeFile('a<b>.txt'))).toBe('a_b_.txt')
    // Backslashes become forward slashes.
    expect(getFileName(makeFile('file.txt', 'folder\\sub\\file.txt'))).toBe(
      'folder/sub/file.txt',
    )
  })

  it('caches the result by file identity (WeakMap)', () => {
    const file = makeFile('CON.txt')
    // First call computes + caches.
    expect(getFileName(file)).toBe('_CON.txt')
    // Mutate file.name after caching — cached result should win.
    ;(file as unknown as { name: string }).name = 'different.txt'
    expect(getFileName(file)).toBe('_CON.txt')
  })

  it('computes fresh for a different file object with the same name', () => {
    const a = makeFile('report.pdf')
    const b = makeFile('report.pdf')
    expect(getFileName(a)).toBe('report.pdf')
    expect(getFileName(b)).toBe('report.pdf')
    // Different identities → different cache entries (verified by
    // mutating one and observing the other is unaffected).
    ;(a as unknown as { name: string }).name = 'changed.pdf'
    // Cached on `a` so still returns the original.
    expect(getFileName(a)).toBe('report.pdf')
    // `b` was never mutated and its cached value stays independent.
    expect(getFileName(b)).toBe('report.pdf')
  })

  it('returns empty string when both entryFullPath and name are absent', () => {
    // ``file.name ?? ''`` handles the undefined case.
    const file = {
      name: undefined,
      entryFullPath: undefined,
    } as unknown as UploadedFile
    expect(getFileName(file)).toBe('')
  })
})
