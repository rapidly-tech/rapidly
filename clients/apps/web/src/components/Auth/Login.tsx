'use client'

import { usePostHog, type EventName } from '@/hooks/posthog'
import { CONFIG } from '@/utils/config'
import { ROUTES } from '@/utils/routes'
import { schemas } from '@rapidly-tech/client'
import LabeledSeparator from '@rapidly-tech/ui/components/layout/LabeledSeparator'
import { usePathname, useSearchParams } from 'next/navigation'
import { useEffect, useMemo } from 'react'
import LoginCodeForm from '../Auth/LoginCodeForm'
import MicrosoftLoginButton from '../Auth/MicrosoftLoginButton'
import AppleLoginButton from './AppleLoginButton'
import GoogleLoginButton from './GoogleLoginButton'

interface LoginProps {
  returnTo?: string
  returnParams?: Record<string, string>
  signup?: schemas['UserSignupAttribution']
}

/**
 * Composite login / signup view.
 * Renders GitHub, Google, and Apple OAuth buttons plus an email-code form.
 * Captures analytics events on view and on provider selection.
 */
const Login = ({ returnTo, returnParams, signup }: LoginProps) => {
  const posthog = usePostHog()
  const pathname = usePathname()
  const searchParams = useSearchParams()

  const eventName: EventName = signup
    ? 'global:user:signup:view'
    : 'global:user:login:view'

  const resolvedReturnTo = useMemo(() => {
    const basePath = returnTo ?? ROUTES.DASHBOARD.ROOT

    if (returnParams) {
      const qs = new URLSearchParams(returnParams)
      if (qs.size) return `${basePath}?${qs}`
    }

    return basePath
  }, [returnTo, returnParams])

  const loginProps = useMemo(() => {
    let eventData = {}

    if (signup) {
      const attribution: Record<string, string | null> = {
        ...signup,
        path: pathname ?? '',
      }

      const host = typeof window !== 'undefined' ? window.location.host : ''
      if (host) attribution.host = host

      for (const key of [
        'campaign',
        'utm_source',
        'utm_medium',
        'utm_campaign',
      ] as const) {
        const val = searchParams.get(key) ?? ''
        if (val) attribution[key] = val
      }

      eventData = { signup: attribution }
    }

    return { returnTo: resolvedReturnTo, ...eventData }
  }, [pathname, resolvedReturnTo, searchParams, signup])

  useEffect(() => {
    posthog.capture(eventName, loginProps)
  }, [eventName, loginProps, posthog])

  return (
    <div className="flex flex-col gap-y-4">
      <div className="flex w-full flex-col gap-y-4">
        <MicrosoftLoginButton
          text="Continue with Microsoft"
          size="large"
          fullWidth
          {...loginProps}
        />
        <GoogleLoginButton {...loginProps} />
        <AppleLoginButton {...loginProps} />
        <LabeledSeparator label="Or" />
        <LoginCodeForm {...loginProps} />
      </div>
      <div className="mt-6 text-center text-xs text-slate-400 dark:text-slate-500">
        By using Rapidly you agree to our{' '}
        <a
          className="text-slate-600 dark:text-slate-300"
          href={CONFIG.LEGAL_TERMS_URL}
        >
          Terms of Service
        </a>{' '}
        and{' '}
        <a
          className="text-slate-600 dark:text-slate-300"
          href={CONFIG.LEGAL_PRIVACY_URL}
        >
          Privacy Policy
        </a>
      </div>
    </div>
  )
}

export default Login
