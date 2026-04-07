/**
 * Formatted price label.
 */
import { formatCurrency } from '@rapidly-tech/currency'
import { Text } from '../Shared/Text'

interface AmountLabelProps {
  amount: number
  currency: string
  loading?: boolean
}

const AmountLabel = ({ amount, currency, loading }: AmountLabelProps) => {
  const formatted = formatCurrency(amount, currency)

  return (
    <Text loading={loading} variant="bodySmall">
      {formatted}
    </Text>
  )
}

export default AmountLabel
