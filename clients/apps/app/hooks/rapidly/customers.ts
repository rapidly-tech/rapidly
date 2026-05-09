import { useRapidlyClient } from '@/providers/RapidlyClientProvider'
import { operations, resolveResponse } from '@rapidly-tech/client'
import { useInfiniteQuery, useQuery } from '@tanstack/react-query'

export const useCustomer = (workspaceId: string | undefined, id: string) => {
  const { rapidly } = useRapidlyClient()

  return useQuery({
    queryKey: ['customers', workspaceId, { id }],
    queryFn: () =>
      resolveResponse(
        rapidly.GET('/api/customers/{id}', {
          params: {
            path: { id },
          },
        }),
      ),
    enabled: !!workspaceId,
  })
}

export const useCustomers = (
  workspaceId: string | undefined,
  parameters?: Omit<
    operations['customers:list_customers_endpoint']['parameters']['query'],
    'workspace_id'
  >,
) => {
  const { rapidly } = useRapidlyClient()

  return useInfiniteQuery({
    queryKey: ['customers', { workspaceId, ...(parameters || {}) }],
    queryFn: ({ pageParam = 1 }) =>
      resolveResponse(
        rapidly.GET('/api/customers/', {
          params: {
            query: {
              workspace_id: workspaceId,
              ...(parameters || {}),
              page: pageParam,
            },
          },
        }),
      ),
    enabled: !!workspaceId,
    initialPageParam: 1,
    getNextPageParam: (lastPage, pages) => {
      if (lastPage.data.length === 0) return undefined
      return pages.length + 1
    },
  })
}
