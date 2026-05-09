/**
 * Home dashboard tile showing the workspace account balance and
 * a withdraw button when the balance exceeds the minimum threshold.
 */
import { Box } from '@/components/Shared/Box'
import {
  useTransactionsSummary,
  useWorkspaceAccount,
} from '@/hooks/rapidly/finance'
import { WorkspaceContext } from '@/providers/WorkspaceProvider'
import { formatCurrency } from '@rapidly-tech/currency'
import { useRouter } from 'expo-router'
import { useContext } from 'react'
import { Button } from '../Shared/Button'
import { Text } from '../Shared/Text'
import { Tile } from './Tile'

export interface FinanceTileProps {
  loading?: boolean
}

const MINIMUM_WITHDRAWAL_CENTS = 1000

export const FinanceTile = ({ loading }: FinanceTileProps) => {
  const { workspace } = useContext(WorkspaceContext)
  const { data: account } = useWorkspaceAccount(workspace?.id)
  const { data: summary } = useTransactionsSummary(account?.id)
  const router = useRouter()

  const balanceAmount = summary?.balance?.amount ?? 0
  const withdrawalAllowed =
    account?.status === 'active' && balanceAmount >= MINIMUM_WITHDRAWAL_CENTS

  const formattedBalance = formatCurrency(balanceAmount, 'usd')

  return (
    <Tile href="/finance">
      <Box flex={1} flexDirection="column" justifyContent="space-between">
        <Box flexDirection="column" gap="spacing-4">
          <Text variant="body" color="subtext">
            Account Balance
          </Text>
          <Text
            variant="headline"
            numberOfLines={1}
            loading={loading}
            placeholderText="$1,234"
          >
            {formattedBalance}
          </Text>
        </Box>
        <Box flexDirection="row" justifyContent="flex-start">
          <Button
            size="small"
            disabled={!withdrawalAllowed}
            onPress={() => router.push('/finance/withdraw')}
          >
            Withdraw
          </Button>
        </Box>
      </Box>
    </Tile>
  )
}
