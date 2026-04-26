import { useRapidlyClient } from '@/providers/RapidlyClientProvider'
import { useSession } from '@/providers/SessionProvider'
import { queryClient } from '@/utils/query'
import { operations, resolveResponse, schemas } from '@rapidly-tech/client'
import {
  useMutation,
  UseMutationResult,
  useQuery,
  useQueryClient,
} from '@tanstack/react-query'

interface WorkspaceDeletionResponse {
  deleted: boolean
  requires_support: boolean
  blocked_reasons: string[]
}

export const useWorkspaces = (
  {
    enabled = true,
  }: {
    enabled?: boolean
  } = { enabled: true },
) => {
  const { rapidly } = useRapidlyClient()

  return useQuery({
    queryKey: ['workspaces'],
    queryFn: () =>
      resolveResponse(
        rapidly.GET('/api/workspaces/', {
          params: {
            query: {
              limit: 100,
            },
          },
        }),
      ),
    enabled,
  })
}

export const useWorkspace = (
  workspaceId?: string,
  parameters?: Omit<
    operations['workspaces:list']['parameters']['query'],
    'workspace_id'
  >,
) => {
  const { rapidly } = useRapidlyClient()

  return useQuery({
    queryKey: ['workspaces', workspaceId, parameters],
    queryFn: () =>
      resolveResponse(
        rapidly.GET('/api/workspaces/', {
          param: {
            query: {
              workspace_id: workspaceId,
              ...(parameters || {}),
            },
          },
        }),
      ),
    enabled: !!workspaceId,
  })
}

export const useCreateWorkspace = () => {
  const { rapidly } = useRapidlyClient()

  return useMutation({
    mutationFn: (workspace: schemas['WorkspaceCreate']) =>
      resolveResponse(
        rapidly.POST('/api/workspaces/', {
          body: workspace,
        }),
      ),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['workspaces'] })
    },
  })
}

export const useUpdateWorkspace = () => {
  const { rapidly } = useRapidlyClient()
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({
      workspaceId,
      update,
    }: {
      workspaceId: string
      update: schemas['WorkspaceUpdate']
    }) => {
      return resolveResponse(
        rapidly.PATCH('/api/workspaces/{id}', {
          params: { path: { id: workspaceId } },
          body: update,
        }),
      )
    },
    onSettled: (data, error, variables, context) => {
      queryClient.invalidateQueries({
        queryKey: ['workspaces'],
      })
    },
  })
}

export const useDeleteWorkspace = (): UseMutationResult<
  { data?: WorkspaceDeletionResponse; error?: { detail: string } },
  Error,
  string
> => {
  const { session } = useSession()

  return useMutation({
    mutationFn: async (workspaceId: string) => {
      const response = await fetch(
        `${process.env.EXPO_PUBLIC_RAPIDLY_SERVER_URL}/api/workspaces/${workspaceId}`,
        {
          method: 'DELETE',
          headers: {
            'Content-Type': 'application/json',
            Authorization: `Bearer ${session}`,
          },
        },
      )

      if (!response.ok) {
        const error = await response.json()
        return { error }
      }

      const data = await response.json()
      return { data }
    },
  })
}
