/**
 * Share price type-guard utilities for the Rapidly mobile app.
 *
 * Helps distinguish between static prices (fixed / custom / free)
 * and legacy recurring prices.
 */
import { schemas } from '@rapidly-tech/client'

type StaticSharePrice =
  | schemas['SharePriceFixed']
  | schemas['SharePriceCustom']
  | schemas['SharePriceFree']

/** Narrows to a static price variant (fixed, custom, or free). */
export const isStaticPrice = (
  price: schemas['SharePrice'],
): price is StaticSharePrice =>
  'amount_type' in price &&
  ['fixed', 'custom', 'free'].includes(price.amount_type)
