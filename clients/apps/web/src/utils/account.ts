import ManualPayout from '@/components/Icons/ManualPayout'
import Stripe from '@/components/Icons/Stripe'
import { schemas } from '@rapidly-tech/client'

type AccountType = schemas['AccountType']

// Human-readable labels for each account provider.
export const ACCOUNT_TYPE_DISPLAY_NAMES: Record<AccountType, string> = {
  stripe: 'Stripe',
  manual: 'Manual',
}

// Maps each account type to the icon component used in lists and banners.
export const ACCOUNT_TYPE_ICON: Record<AccountType, React.FC> = {
  stripe: Stripe,
  manual: ManualPayout,
}
