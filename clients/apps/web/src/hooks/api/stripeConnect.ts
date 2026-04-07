import { api } from '@/utils/client'
import { resolveResponse } from '@rapidly-tech/client'
import { useQuery } from '@tanstack/react-query'
import { baseRetry } from './retry'

/** Fetches the Stripe Connect balance for an workspace. */
export const useStripeBalance = (workspaceId?: string) =>
  useQuery({
    queryKey: ['stripe-connect', 'balance', workspaceId],
    queryFn: () =>
      resolveResponse(
        api.GET('/api/stripe-connect/balance', {
          params: {
            query: { workspace_id: workspaceId as string },
          },
        }),
      ),
    retry: baseRetry,
    enabled: !!workspaceId,
  })

/** Fetches the list of Stripe Connect payouts for an workspace. */
export const useStripePayouts = (
  workspaceId?: string,
  params?: {
    created_gte?: string
    created_lte?: string
    limit?: number
    starting_after?: string
  },
) =>
  useQuery({
    queryKey: ['stripe-connect', 'payouts', workspaceId, params],
    queryFn: () =>
      resolveResponse(
        api.GET('/api/stripe-connect/payouts', {
          params: {
            query: {
              workspace_id: workspaceId as string,
              created_gte: params?.created_gte ?? undefined,
              created_lte: params?.created_lte ?? undefined,
              limit: params?.limit ?? undefined,
              starting_after: params?.starting_after ?? undefined,
            },
          },
        }),
      ),
    retry: baseRetry,
    enabled: !!workspaceId,
  })
