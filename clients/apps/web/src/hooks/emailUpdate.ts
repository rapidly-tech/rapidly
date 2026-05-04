'use client'

import { api } from '@/utils/client'
import { useCallback } from 'react'

/**
 * Hook that returns a memoised callback for initiating an email-change
 * verification flow. The backend sends a confirmation link to the new
 * address; `return_to` controls where the user lands after confirming.
 */
export const useSendEmailUpdate = () => {
  const requestEmailChange = useCallback(
    (email: string, return_to?: string) =>
      api.POST('/api/email-update/request', {
        body: { email, return_to },
      }),
    [],
  )

  return requestEmailChange
}
