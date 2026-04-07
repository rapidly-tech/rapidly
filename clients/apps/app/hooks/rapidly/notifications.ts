import { useRapidlyClient } from '@/providers/RapidlyClientProvider'
import { useSession } from '@/providers/SessionProvider'
import { queryClient } from '@/utils/query'
import { resolveResponse, schemas } from '@rapidly-tech/client'
import { useMutation, useQuery, UseQueryResult } from '@tanstack/react-query'
import { Platform } from 'react-native'

export interface NotificationRecipient {
  id: string
  expo_push_token: string
  platform: 'ios' | 'android'
  created_at: string
  updated_at: string
}

export const useCreateNotificationRecipient = () => {
  const { rapidly } = useRapidlyClient()

  return useMutation({
    mutationFn: async (expoPushToken: string) => {
      return resolveResponse(
        rapidly.POST('/api/notifications/recipients', {
          body: {
            expo_push_token: expoPushToken,
            platform: Platform.OS as 'ios' | 'android',
          },
        }),
      )
    },
    onSuccess: (result, variables, context) => {
      queryClient.invalidateQueries({ queryKey: ['notification_recipient'] })
      queryClient.invalidateQueries({ queryKey: ['notification_recipients'] })
    },
  })
}

export const useListNotificationRecipients = () => {
  const { rapidly } = useRapidlyClient()

  return useQuery({
    queryKey: ['notification_recipients'],
    queryFn: async () => {
      return resolveResponse(rapidly.GET('/api/notifications/recipients'))
    },
  })
}

export const useGetNotificationRecipient = (
  expoPushToken: string | undefined,
) => {
  const { session } = useSession()
  const { rapidly } = useRapidlyClient()

  return useQuery({
    queryKey: ['notification_recipient', expoPushToken],
    queryFn: async () => {
      const response = await resolveResponse(
        rapidly.GET('/api/notifications/recipients', {
          params: {
            query: {
              expo_push_token: expoPushToken,
            },
          },
        }),
      )

      return response.data?.[0] ?? null
    },
    enabled: !!expoPushToken && !!session,
  })
}

export const useDeleteNotificationRecipient = () => {
  const { rapidly } = useRapidlyClient()

  return useMutation({
    mutationFn: async (id: string) => {
      return rapidly
        .DELETE('/api/notifications/recipients/{id}', {
          params: {
            path: {
              id,
            },
          },
        })
        .finally(() => {
          queryClient.invalidateQueries({
            queryKey: ['notification_recipients'],
          })
          queryClient.invalidateQueries({
            queryKey: ['notification_recipient'],
          })
        })
    },
  })
}

export type Notification = schemas['NotificationsList']['notifications'][number]

export const useListNotifications = (): UseQueryResult<
  schemas['NotificationsList'],
  Error
> => {
  const { session } = useSession()

  return useQuery({
    queryKey: ['notifications'],
    queryFn: async () => {
      const response = await fetch(
        `${process.env.EXPO_PUBLIC_RAPIDLY_SERVER_URL}/api/notifications`,
        {
          headers: {
            'Content-Type': 'application/json',
            Authorization: `Bearer ${session}`,
          },
        },
      )

      return response.json()
    },
  })
}

export const useNotificationsMarkRead = () => {
  const { session } = useSession()

  return useMutation({
    mutationFn: async (variables: { notificationId: string }) => {
      const response = await fetch(
        `${process.env.EXPO_PUBLIC_RAPIDLY_SERVER_URL}/api/notifications/read`,
        {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            Authorization: `Bearer ${session}`,
          },
          body: JSON.stringify({
            notification_id: variables.notificationId,
          }),
        },
      )

      return response.json()
    },
    onSuccess: (result, _variables, _ctx) => {
      if (result && 'error' in result && result.error) {
        return
      }

      queryClient.invalidateQueries({ queryKey: ['notifications'] })
    },
  })
}
