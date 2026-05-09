import { useRapidlyClient } from '@/providers/RapidlyClientProvider'
import { queryClient } from '@/utils/query'
import { operations, resolveResponse, schemas } from '@rapidly-tech/client'
import { useInfiniteQuery, useMutation, useQuery } from '@tanstack/react-query'

export const useShare = (
  workspaceId: string | undefined,
  id: string | undefined,
) => {
  const { rapidly } = useRapidlyClient()

  return useQuery({
    queryKey: ['share', workspaceId, { id }],
    queryFn: () =>
      resolveResponse(
        rapidly.GET('/api/shares/{id}', {
          params: { path: { id: id ?? '' } },
        }),
      ),
    enabled: !!workspaceId && !!id,
  })
}

export const useShares = (
  workspaceId: string | undefined,
  options: Omit<
    NonNullable<operations['shares:list']['parameters']['query']>,
    'workspace_id'
  >,
) => {
  const { rapidly } = useRapidlyClient()

  return useQuery({
    queryKey: ['shares', workspaceId, { ...options }],
    queryFn: () =>
      resolveResponse(
        rapidly.GET('/api/shares/', {
          params: { query: { workspace_id: workspaceId, ...options } },
        }),
      ),
  })
}

export const useInfiniteShares = (
  workspaceId: string | undefined,
  options?: Omit<
    NonNullable<operations['shares:list']['parameters']['query']>,
    'workspace_id'
  >,
) => {
  const { rapidly } = useRapidlyClient()

  return useInfiniteQuery({
    queryKey: ['infinite', 'shares', workspaceId, { ...options }],
    queryFn: ({ pageParam = 1 }) =>
      resolveResponse(
        rapidly.GET('/api/shares/', {
          params: {
            query: {
              workspace_id: workspaceId,
              ...options,
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

export const useShareUpdate = (workspaceId: string | undefined, id: string) => {
  const { rapidly } = useRapidlyClient()

  return useMutation({
    mutationFn: (data: schemas['ShareUpdate']) =>
      resolveResponse(
        rapidly.PATCH('/api/shares/{id}', {
          params: { path: { id } },
          body: data,
        }),
      ),
    onSuccess: (data, variables) => {
      queryClient.setQueryData(['share', workspaceId, { id }], data)

      queryClient.invalidateQueries({
        queryKey: ['shares', workspaceId],
      })

      queryClient.invalidateQueries({
        queryKey: ['infinite', 'shares', workspaceId],
      })
    },
  })
}
