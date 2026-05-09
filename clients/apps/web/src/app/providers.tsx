'use client'

import { cookieConsentGiven } from '@/components/Privacy/CookieConsent'
import { registerSolarIcons } from '@/lib/solar-icons.generated'
import { getQueryClient } from '@/utils/api/query'
import { CONFIG } from '@/utils/config'
import { QueryClientProvider } from '@tanstack/react-query'
import { ThemeProvider as NextThemeProvider } from 'next-themes'
import { usePathname, useSearchParams } from 'next/navigation'
import { NuqsAdapter } from 'nuqs/adapters/next/app'
import posthog from 'posthog-js'
import { PostHogProvider } from 'posthog-js/react'
import { type PropsWithChildren, useEffect, useRef } from 'react'

// Defer icon registration to after first paint
let _iconsRegistered = false
function ensureIcons() {
  if (!_iconsRegistered) {
    registerSolarIcons()
    _iconsRegistered = true
  }
}

// ── URL state ───────────────────────────────────────────────────────

export function URLStateProvider({ children }: PropsWithChildren) {
  const registered = useRef(false)
  useEffect(() => {
    if (!registered.current) {
      ensureIcons()
      registered.current = true
    }
  }, [])
  return <NuqsAdapter>{children}</NuqsAdapter>
}

// ── Data fetching ───────────────────────────────────────────────────

export function QueryProvider({ children }: { children: React.ReactNode }) {
  const queryClient = getQueryClient()

  return (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  )
}

// ── Theming ─────────────────────────────────────────────────────────

const DARK_FORCED_PATHS = ['/portal', '/share/'] as const

export function ThemeProvider({
  children,
  forceTheme,
  nonce,
}: {
  children: React.ReactNode
  forceTheme?: 'light' | 'dark'
  nonce?: string
}) {
  const pathname = usePathname()
  const searchParams = useSearchParams()
  const themeParam = searchParams.get('theme')
  const validTheme =
    themeParam === 'light' || themeParam === 'dark' || themeParam === 'system'
      ? themeParam
      : undefined

  const forcedTheme = DARK_FORCED_PATHS.some((p) => pathname.includes(p))
    ? 'dark'
    : forceTheme

  return (
    <NextThemeProvider
      defaultTheme="system"
      enableSystem
      attribute="class"
      forcedTheme={validTheme ?? forcedTheme}
      nonce={nonce}
    >
      {children}
    </NextThemeProvider>
  )
}

// ── Analytics ───────────────────────────────────────────────────────

function initPostHog(distinctId: string): void {
  if (!CONFIG.POSTHOG_TOKEN) return

  const consent = cookieConsentGiven()

  posthog.init(CONFIG.POSTHOG_TOKEN, {
    api_host: '/ingest',
    ui_host: 'https://us.i.posthog.com',
    defaults: '2025-05-24',
    persistence: consent === 'yes' ? 'localStorage' : 'memory',
    bootstrap: { distinctID: distinctId },
  })
}

export function AnalyticsProvider({
  children,
  distinctId,
}: {
  children: React.ReactNode
  distinctId: string
}) {
  useEffect(() => {
    // Defer analytics init to idle time to reduce TBT
    const init = () => initPostHog(distinctId)
    if ('requestIdleCallback' in window) {
      requestIdleCallback(init)
    } else {
      setTimeout(init, 1)
    }
  }, [distinctId])

  return <PostHogProvider client={posthog}>{children}</PostHogProvider>
}
