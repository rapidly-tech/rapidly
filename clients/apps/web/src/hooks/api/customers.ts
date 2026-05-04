import { getQueryClient } from '@/utils/api/query'
import { api } from '@/utils/client'
import { schemas } from '@rapidly-tech/client'
import { useMutation } from '@tanstack/react-query'

// Shared cache key helpers
const customersKey = (workspaceId: string) => ['customers', workspaceId]

/**
 * Patches an existing customer then refreshes caches scoped to the
 * customer's workspace.
 */
export const useUpdateCustomer = (customerId: string, workspaceId: string) =>
  useMutation({
    mutationFn: (body: schemas['CustomerUpdate']) =>
      api.PATCH('/api/customers/{id}', {
        params: { path: { id: customerId } },
        body,
      }),
    onSuccess: () => {
      getQueryClient().invalidateQueries({
        queryKey: customersKey(workspaceId),
      })
    },
  })
