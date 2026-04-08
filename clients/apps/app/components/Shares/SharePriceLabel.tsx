/**
 * Resolves the display price for a share in the given currency.
 *
 * Finds the first matching static price (fixed / custom / free) and
 * renders an AmountLabel, "Pay what you want", or "Free" accordingly.
 */
import { schemas } from '@rapidly-tech/client'
import { Text } from '../Shared/Text'
import AmountLabel from './AmountLabel'

interface SharePriceLabelProps {
  currency: string
  share?: schemas['Share']
  loading?: boolean
}

const STATIC_AMOUNT_TYPES = ['fixed', 'custom', 'free']

export const SharePriceLabel = ({
  currency,
  share,
  loading,
}: SharePriceLabelProps) => {
  const matchedPrice = share?.prices.find(
    (price) =>
      'price_currency' in price &&
      'amount_type' in price &&
      price.price_currency === currency &&
      STATIC_AMOUNT_TYPES.includes(price.amount_type),
  )

  if (!matchedPrice || !('amount_type' in matchedPrice)) return null

  if (matchedPrice.amount_type === 'fixed' && 'price_amount' in matchedPrice) {
    return (
      <AmountLabel
        amount={matchedPrice.price_amount}
        currency={
          'price_currency' in matchedPrice
            ? matchedPrice.price_currency
            : currency
        }
        loading={loading}
      />
    )
  }

  if (matchedPrice.amount_type === 'custom') {
    return <Text loading={loading}>Pay what you want</Text>
  }

  return <Text loading={loading}>Free</Text>
}
