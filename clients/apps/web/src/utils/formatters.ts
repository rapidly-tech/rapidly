import { getCurrencyDecimalFactor } from '@rapidly-tech/currency'

// ── Helpers ──

const stripTrailingZeros = (value: string): string => {
  return value.replace(/\.0+([^0-9]*)$/g, '$1')
}

// ── Cached Currency Formatter Factory ──

/**
 * Creates a currency formatting function that lazily builds and caches
 * an `Intl.NumberFormat` per currency code using the supplied options callback.
 *
 * @param getOptions - receives the resolved fraction-digit count and the
 *   original currency string; must return the `Intl.NumberFormatOptions` for
 *   the formatter to cache.
 */
const createCachedCurrencyFormatter = (
  getOptions: (
    fractionDigits: number,
    currency: string,
  ) => Intl.NumberFormatOptions,
): ((value: number, currency: string) => string) => {
  const cache: Record<string, Intl.NumberFormat> = {}
  return (value: number, currency: string): string => {
    const key = currency.toLowerCase()
    const decimalFactor = getCurrencyDecimalFactor(key)
    if (!cache[key]) {
      const fractionDigits = decimalFactor === 1 ? 0 : 2
      cache[key] = new Intl.NumberFormat(
        'en-US',
        getOptions(fractionDigits, currency),
      )
    }
    return stripTrailingZeros(cache[key].format(value / decimalFactor))
  }
}

/**
 * Like `createCachedCurrencyFormatter` but maintains *two* formatters per
 * currency: one for values below a threshold and one (compact) for values
 * above it.
 */
const createCompactCurrencyFormatter = (
  threshold: number,
  getSmallOptions: (
    fractionDigits: number,
    currency: string,
  ) => Intl.NumberFormatOptions,
  getLargeOptions: (
    fractionDigits: number,
    currency: string,
  ) => Intl.NumberFormatOptions,
): ((value: number, currency: string) => string) => {
  const smallCache: Record<string, Intl.NumberFormat> = {}
  const largeCache: Record<string, Intl.NumberFormat> = {}
  return (value: number, currency: string): string => {
    const key = currency.toLowerCase()
    const decimalFactor = getCurrencyDecimalFactor(key)
    const fractionDigits = decimalFactor === 1 ? 0 : 2
    if (!smallCache[key]) {
      smallCache[key] = new Intl.NumberFormat(
        'en-US',
        getSmallOptions(fractionDigits, currency),
      )
    }
    if (!largeCache[key]) {
      largeCache[key] = new Intl.NumberFormat(
        'en-US',
        getLargeOptions(fractionDigits, currency),
      )
    }
    const fmt =
      value > threshold * decimalFactor ? largeCache[key] : smallCache[key]
    return stripTrailingZeros(fmt.format(value / decimalFactor))
  }
}

// ── Scalar Formatters ──

export const formatScalar = (() => {
  const formatter = new Intl.NumberFormat('en-US', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })

  return (value: number): string => stripTrailingZeros(formatter.format(value))
})()

// ── Percentage Formatter ──

export const formatPercentage = (() => {
  const formatter = new Intl.NumberFormat('en-US', {
    style: 'percent',
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })

  return (value: number): string => stripTrailingZeros(formatter.format(value))
})()

// ── Currency Formatters ──

// Turns $23,456.78 into $23.456K and $1,234,876.54 into $1.234M (threshold 10k, three decimal places)
export const formatAccountingFriendlyCurrency = createCompactCurrencyFormatter(
  10_000,
  (fractionDigits, currency) => ({
    style: 'currency',
    currency,
    minimumFractionDigits: fractionDigits,
    maximumFractionDigits: fractionDigits,
  }),
  (_fractionDigits, currency) => ({
    style: 'currency',
    currency,
    minimumFractionDigits: 3,
    maximumFractionDigits: 3,
    notation: 'compact',
    compactDisplay: 'short',
  }),
)

export const formatSubCentCurrency = createCachedCurrencyFormatter(
  (fractionDigits, currency) => ({
    style: 'currency',
    currency,
    minimumFractionDigits: fractionDigits === 0 ? 0 : 4,
    maximumFractionDigits: fractionDigits === 0 ? 0 : 4,
  }),
)
