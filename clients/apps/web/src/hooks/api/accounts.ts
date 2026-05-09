import { api } from '@/utils/client'
import { resolveResponse, schemas } from '@rapidly-tech/client'
import { UseQueryResult, useQuery } from '@tanstack/react-query'
import { baseRetry } from './retry'

type AccountList = schemas['PaginatedList_Account_']

/**
 * Retrieves all payout accounts belonging to the authenticated user.
 */
export const useListAccounts: () => UseQueryResult<AccountList> = () =>
  useQuery({
    queryKey: ['user', 'accounts'],
    queryFn: async () => resolveResponse(api.GET('/api/accounts/search')),
    retry: baseRetry,
  })
