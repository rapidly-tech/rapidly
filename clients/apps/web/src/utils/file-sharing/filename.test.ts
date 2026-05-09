import { describe, expect, it } from 'vitest'

import { sanitizeFileName } from './filename'

describe('sanitizeFileName', () => {
  it('returns benign names untouched', () => {
    expect(sanitizeFileName('report.pdf')).toBe('report.pdf')
    expect(sanitizeFileName('a/b/c.txt')).toBe('a/b/c.txt')
    expect(sanitizeFileName('has spaces.md')).toBe('has spaces.md')
  })

  it('normalizes backslashes to forward slashes', () => {
    expect(sanitizeFileName('foo\\bar\\baz.txt')).toBe('foo/bar/baz.txt')
  })

  it('replaces Windows-unsafe characters with underscores', () => {
    expect(sanitizeFileName('a<b>c:d"e|f?g*h.txt')).toBe('a_b_c_d_e_f_g_h.txt')
  })

  it('prefixes Windows reserved device names with an underscore', () => {
    expect(sanitizeFileName('CON')).toBe('_CON')
    expect(sanitizeFileName('con')).toBe('_con') // case-insensitive match
    expect(sanitizeFileName('PRN.txt')).toBe('_PRN.txt')
    expect(sanitizeFileName('aux.json')).toBe('_aux.json')
    expect(sanitizeFileName('NUL.log')).toBe('_NUL.log')
  })

  it('prefixes numbered reserved names (COM1-9, LPT1-9)', () => {
    expect(sanitizeFileName('COM1')).toBe('_COM1')
    expect(sanitizeFileName('com9.dat')).toBe('_com9.dat')
    expect(sanitizeFileName('LPT1')).toBe('_LPT1')
    expect(sanitizeFileName('lpt5.tmp')).toBe('_lpt5.tmp')
  })

  it('does not prefix names that merely start with a reserved prefix', () => {
    // "CONFIG" starts with "CON" but isn't reserved — only the bare name
    // or "name.ext" form is Windows-reserved.
    expect(sanitizeFileName('CONFIG')).toBe('CONFIG')
    expect(sanitizeFileName('AUXILIARY.txt')).toBe('AUXILIARY.txt')
    expect(sanitizeFileName('COM10.txt')).toBe('COM10.txt')
  })

  it('sanitizes each path segment independently', () => {
    expect(sanitizeFileName('safe/CON/file.txt')).toBe('safe/_CON/file.txt')
    expect(sanitizeFileName('CON/AUX')).toBe('_CON/_AUX')
  })

  it('handles reserved names after backslash-normalization', () => {
    expect(sanitizeFileName('dir\\CON.txt')).toBe('dir/_CON.txt')
  })

  it('combines unsafe-char replacement + reserved-name prefixing', () => {
    expect(sanitizeFileName('foo?bar/CON')).toBe('foo_bar/_CON')
  })

  it('returns empty string for empty input', () => {
    expect(sanitizeFileName('')).toBe('')
  })
})
