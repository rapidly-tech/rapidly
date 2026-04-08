import { getQueryClient } from '@/utils/api/query'
import { api } from '@/utils/client'
import { resolveResponse } from '@rapidly-tech/client'
import { useMutation, useQuery } from '@tanstack/react-query'
import { baseRetry } from './retry'

export * from './accounts'
export * from './customerPortal'
export * from './customers'
export * from './metrics'
export * from './org'

export * from './webhooks'

export const useNotifications = () =>
  useQuery({
    queryKey: ['notifications'],
    queryFn: () => resolveResponse(api.GET('/api/notifications')),
    retry: baseRetry,
  })

export const useNotificationsMarkRead = () =>
  useMutation({
    mutationFn: (variables: { notification_id: string }) => {
      return api.POST('/api/notifications/read', {
        body: {
          notification_id: variables.notification_id,
        },
      })
    },
    onSuccess: (result, _variables, _ctx) => {
      if (result.error) {
        return
      }
      getQueryClient().invalidateQueries({ queryKey: ['notifications'] })
    },
  })
