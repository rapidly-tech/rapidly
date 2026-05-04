'use client'

import { api } from '@/utils/client'
import { schemas } from '@rapidly-tech/client'
import { useRouter } from 'next/navigation'
import { useCallback } from 'react'

type ValidationDetail = schemas['ValidationError'][] | undefined

/**
 * Wraps validation failures from the login-code request endpoint
 * so callers can inspect individual field errors.
 */
export class LoginCodeError extends Error {
  error: ValidationDetail

  constructor(detail: ValidationDetail) {
    super('Login Code Error')
    this.name = 'LoginCodeError'
    this.error = detail
  }
}

/**
 * Provides a stable callback that requests a one-time login code for the
 * given email address, then redirects the browser to the verification page.
 *
 * The optional `return_to` path is forwarded as a query parameter so the
 * verification page can redirect back after success.
 */
export const useSendLoginCode = () => {
  const router = useRouter()

  return useCallback(
    async (
      email: string,
      return_to?: string,
      signup?: schemas['UserSignupAttribution'],
    ) => {
      const result = await api.POST('/api/login-code/request', {
        body: { email, return_to, attribution: signup },
      })

      if (result.error) {
        throw new LoginCodeError(result.error.detail)
      }

      // Build the verification URL with the user's email and optional redirect
      const params = new URLSearchParams()
      params.set('email', email)
      if (return_to) {
        params.set('return_to', return_to)
      }

      router.push(`/login/code/verify?${params.toString()}`)
    },
    [router],
  )
}
