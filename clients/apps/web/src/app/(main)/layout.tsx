import { CookieConsent } from '@/components/Privacy/CookieConsent'
import { Toaster } from '@/components/Toast/Toaster'
import { headers } from 'next/headers'
import { PropsWithChildren, Suspense } from 'react'
import { ThemeProvider } from '../providers'

const MAIN_WRAPPER_CLASSES = 'min-h-dvh rp-page-bg rp-text-primary'

export default async function Layout({ children }: PropsWithChildren) {
  const headersList = await headers()
  const countryCode = headersList.get('x-vercel-ip-country')
  const nonce = headersList.get('x-nonce') ?? undefined

  return (
    <ThemeProvider nonce={nonce}>
      <div className={MAIN_WRAPPER_CLASSES}>
        {children}
        <CookieConsent countryCode={countryCode} />
        <Suspense fallback={null}>
          <Toaster />
        </Suspense>
      </div>
    </ThemeProvider>
  )
}
