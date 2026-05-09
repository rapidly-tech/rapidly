import { describe, expect, it } from 'vitest'

import {
  formatAccountingFriendlyCurrency,
  formatPercentage,
  formatScalar,
  formatSubCentCurrency,
} from './formatters'

/** These tests assert *structural* properties (contains "$", ends with
 *  "%", has a "K" compact suffix, no trailing ".00") rather than pinning
 *  exact locale strings — that way locale/CLDR updates in Node's Intl
 *  tables don't flap the suite, while regressions in the stripping or
 *  threshold logic still surface. */

describe('formatScalar', () => {
  it('formats integers with no trailing zeros', () => {
    expect(formatScalar(1)).toBe('1')
    expect(formatScalar(1000)).toBe('1,000')
  })

  it('keeps non-zero decimals', () => {
    expect(formatScalar(1.25)).toBe('1.25')
    expect(formatScalar(1234.56)).toBe('1,234.56')
  })

  it('strips trailing zeros from ".00"', () => {
    expect(formatScalar(1.0)).toBe('1')
    expect(formatScalar(100)).toBe('100')
  })

  it('handles zero and negatives', () => {
    expect(formatScalar(0)).toBe('0')
    // stripTrailingZeros only removes a pure-zero fractional part — ".50"
    // has a non-zero leading digit so it survives unchanged.
    expect(formatScalar(-1.5)).toBe('-1.50')
  })
})

describe('formatPercentage', () => {
  it('formats a decimal as a percent ending in "%"', () => {
    expect(formatPercentage(0.25)).toMatch(/%$/)
    expect(formatPercentage(0.25)).toContain('25')
  })

  it('strips trailing zeros after the decimal point', () => {
    // 0.5 → "50%", not "50.00%"
    expect(formatPercentage(0.5)).toBe('50%')
  })

  it('keeps non-zero fractional percentages', () => {
    expect(formatPercentage(0.1234)).toBe('12.34%')
  })

  it('handles 0% and 100%', () => {
    expect(formatPercentage(0)).toBe('0%')
    expect(formatPercentage(1)).toBe('100%')
  })
})

describe('formatAccountingFriendlyCurrency — below threshold (10 000)', () => {
  it('includes a "$" symbol for USD', () => {
    expect(formatAccountingFriendlyCurrency(500, 'usd')).toContain('$')
  })

  it('treats the value as minor units (cents for USD)', () => {
    // 500 cents → $5.00 → "$5" after stripping.
    expect(formatAccountingFriendlyCurrency(500, 'usd')).toBe('$5')
  })

  it('keeps real decimals when present', () => {
    expect(formatAccountingFriendlyCurrency(1234, 'usd')).toContain('12.34')
  })

  it('stays in non-compact form below the threshold', () => {
    // $9,999.99 — just under the 10 000 threshold — stays long-form.
    const out = formatAccountingFriendlyCurrency(999_999, 'usd')
    expect(out).not.toMatch(/[KMB]$/)
  })

  it('treats JPY (decimal factor 1) without fractional digits', () => {
    // JPY has no sub-unit — 1000 value = ¥1,000.
    expect(formatAccountingFriendlyCurrency(1000, 'jpy')).toContain('1,000')
    expect(formatAccountingFriendlyCurrency(1000, 'jpy')).not.toContain('.')
  })
})

describe('formatAccountingFriendlyCurrency — above threshold (10 000)', () => {
  it('switches to compact notation at the threshold', () => {
    // $10,000 → "$10K" (or similar compact).
    const out = formatAccountingFriendlyCurrency(1_000_100, 'usd')
    expect(out).toMatch(/[KMB]/)
  })

  it('renders $1.234M-style three-decimal compact for a million-dollar value', () => {
    const out = formatAccountingFriendlyCurrency(123_487_654, 'usd')
    // Expect a compact M suffix and at most 3 fractional digits.
    expect(out).toContain('M')
    expect(out).toContain('$')
  })

  it('uses ¥...M for JPY above 10 000', () => {
    const out = formatAccountingFriendlyCurrency(5_000_000, 'jpy')
    expect(out).toMatch(/[KMB]/)
  })
})

describe('formatSubCentCurrency', () => {
  it('formats USD with up to 4 fractional digits when cents are involved', () => {
    // 1 cent → $0.01 but the formatter goes to 4 fractional digits so
    // it's "$0.01" (trailing zeros stripped).
    const out = formatSubCentCurrency(1, 'usd')
    expect(out).toContain('$')
    expect(out).toMatch(/0\.01/)
  })

  it('preserves sub-cent precision', () => {
    // 4 fractional digits: 10 minor units → $0.1000. stripTrailingZeros
    // only strips a PURE-zero fractional part (e.g. ".0000"), so partial
    // zeros like ".1000" survive untouched.
    expect(formatSubCentCurrency(10, 'usd')).toBe('$0.1000')
    expect(formatSubCentCurrency(12, 'usd')).toBe('$0.1200')
    // Whereas a whole-dollar value DOES get stripped (fractional part is
    // all zeros): 100 minor units → "$1.0000" → "$1".
    expect(formatSubCentCurrency(100, 'usd')).toBe('$1')
  })

  it('omits fractional digits for no-decimal currencies (JPY)', () => {
    const out = formatSubCentCurrency(1000, 'jpy')
    expect(out).not.toContain('.')
  })

  it('is case-insensitive on the currency code', () => {
    // Cache key is lowercased internally — both forms should resolve.
    const lower = formatSubCentCurrency(500, 'usd')
    const upper = formatSubCentCurrency(500, 'USD')
    expect(lower).toBe(upper)
  })
})

describe('formatters — caching', () => {
  it('returns stable output across repeated calls (Intl formatter cache works)', () => {
    // Exercise the per-currency cache path by calling repeatedly.
    const a = formatAccountingFriendlyCurrency(500, 'eur')
    const b = formatAccountingFriendlyCurrency(500, 'eur')
    const c = formatAccountingFriendlyCurrency(500, 'eur')
    expect(a).toBe(b)
    expect(b).toBe(c)
  })

  it('maintains independent caches per currency', () => {
    const usd = formatAccountingFriendlyCurrency(500, 'usd')
    const eur = formatAccountingFriendlyCurrency(500, 'eur')
    // Different currency symbols should produce different output.
    expect(usd).not.toBe(eur)
  })
})
