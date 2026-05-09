import { api } from '@/utils/client'
import { resolveResponse } from '@rapidly-tech/client'
import { useQuery } from '@tanstack/react-query'
import { baseRetry } from './retry'

const RECIPIENTS_KEY = ['notification_recipients'] as const

/**
 * Loads every notification recipient configured for the current user.
 */
export const useListNotificationRecipients = () =>
  useQuery({
    queryKey: [...RECIPIENTS_KEY],
    queryFn: () => resolveResponse(api.GET('/api/notifications/recipients')),
    retry: baseRetry,
  })
