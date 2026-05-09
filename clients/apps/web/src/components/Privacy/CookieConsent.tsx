'use client'

import { EU_COUNTRY_CODES } from '@/components/Privacy/countries'
import { usePostHog } from '@/hooks/posthog'
import { LocalStorageKey } from '@/hooks/upsell'
import { useSearchParams } from 'next/navigation'
import { useCallback, useEffect, useState } from 'react'

type ConsentState = 'undecided' | 'yes' | 'no'

const CONSENT_KEY = LocalStorageKey.COOKIE_CONSENT

const readConsent = (): ConsentState => {
  if (typeof window === 'undefined' || typeof localStorage === 'undefined') {
    return 'undecided'
  }
  const stored = localStorage.getItem(CONSENT_KEY)
  if (!stored) return 'undecided'
  return stored as ConsentState
}

export function cookieConsentGiven(): string {
  return readConsent()
}

const persistConsent = (value: ConsentState): void => {
  localStorage.setItem(CONSENT_KEY, value)
}

const extractDoNotTrack = (params: URLSearchParams): string | null => {
  const direct = params.get('do_not_track')
  if (direct) return direct

  const returnTo = params.get('return_to')
  if (!returnTo) return null

  try {
    const returnUrl = new URL(returnTo, window.location.origin)
    return returnUrl.searchParams.get('do_not_track')
  } catch {
    return null
  }
}

const BANNER_CLASSES =
  'shadow-3xl glass-card fixed right-8 bottom-8 left-8 z-50 flex flex-col gap-y-4 rounded-2xl p-4 text-sm rp-text-secondary md:left-auto md:max-w-96'

const ACCEPT_CLASSES =
  'cursor-pointer rp-text-primary transition-colors dark:hover:text-slate-200'

const DECLINE_CLASSES =
  'cursor-pointer text-slate-500 transition-colors hover:text-slate-600 dark:hover:text-slate-600'

const isEUCountry = (code: string | null): boolean =>
  code ? EU_COUNTRY_CODES.includes(code) : false

export function CookieConsent({ countryCode }: { countryCode: string | null }) {
  const isEU = isEUCountry(countryCode)
  const [consentGiven, setConsentGiven] = useState<string>('')
  const { setPersistence } = usePostHog()
  const searchParams = useSearchParams()

  const doNotTrackParam = extractDoNotTrack(searchParams)

  const declineCookies = useCallback(() => {
    persistConsent('no')
    setConsentGiven('no')
  }, [])

  const acceptCookies = useCallback(() => {
    persistConsent('yes')
    setConsentGiven('yes')
  }, [])

  useEffect(() => {
    const currentConsent = readConsent()

    if (doNotTrackParam && currentConsent === 'undecided') {
      declineCookies()
    } else {
      setConsentGiven(currentConsent)
    }
  }, [declineCookies, doNotTrackParam])

  useEffect(() => {
    if (consentGiven !== '') {
      const mode = consentGiven === 'yes' ? 'localStorage' : 'memory'
      setPersistence(mode)
    }
  }, [consentGiven, setPersistence])

  if (!isEU || doNotTrackParam) return null
  if (consentGiven !== 'undecided') return null

  return (
    <div className={BANNER_CLASSES}>
      <p>
        We use tracking cookies to understand how you use the product and help
        us improve it.
      </p>
      <div className="flex flex-row items-center gap-x-4">
        <button
          className={ACCEPT_CLASSES}
          onClick={acceptCookies}
          type="button"
        >
          Accept
        </button>
        <button
          className={DECLINE_CLASSES}
          onClick={declineCookies}
          type="button"
        >
          Decline
        </button>
      </div>
    </div>
  )
}
