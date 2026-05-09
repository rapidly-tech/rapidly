import '../styles/globals.css'

import SandboxBanner from '@/components/Sandbox/SandboxBanner'
import { UserContextProvider } from '@/providers/auth'
import { getServerSideAPI } from '@/utils/client/serverside'
import { CONFIG } from '@/utils/config'
import { getDistinctId } from '@/utils/distinct-id'
import { getAuthenticatedUser, getWorkspaceMemberships } from '@/utils/user'
import { schemas } from '@rapidly-tech/client'
import { GeistMono } from 'geist/font/mono'
import { GeistSans } from 'geist/font/sans'
import { PHASE_PRODUCTION_BUILD } from 'next/constants'
import { headers } from 'next/headers'
import { Metadata } from 'next/types'
import { AnalyticsProvider, QueryProvider, URLStateProvider } from './providers'

export async function generateMetadata(): Promise<Metadata> {
  const baseMetadata: Metadata = {
    title: {
      template: '%s | Rapidly',
      default: 'Rapidly',
    },
    description:
      'Share files securely with encryption, optional payments, and full analytics.',
    openGraph: {
      images: CONFIG.OG_IMAGE_URL,
      type: 'website',
      siteName: 'Rapidly',
      title: 'Rapidly | Secure File Sharing',
      description:
        'Share files securely with encryption, optional payments, and full analytics.',
      locale: 'en_US',
    },
    twitter: {
      images: CONFIG.OG_IMAGE_URL,
      card: 'summary_large_image',
      title: 'Rapidly | Secure File Sharing',
      description:
        'Share files securely with encryption, optional payments, and full analytics.',
    },
    metadataBase: new URL(CONFIG.FRONTEND_BASE_URL),
    alternates: {
      canonical: CONFIG.FRONTEND_BASE_URL,
    },
  }

  // Environment-specific metadata
  if (CONFIG.IS_SANDBOX) {
    return {
      ...baseMetadata,
      robots: {
        index: false,
        follow: false,
        googleBot: {
          index: false,
          follow: false,
        },
      },
    }
  }

  return {
    ...baseMetadata,
    robots: {
      index: true,
      follow: true,
      googleBot: {
        index: true,
        follow: true,
        'max-video-preview': -1,
        'max-image-preview': 'large',
        'max-snippet': -1,
      },
    },
  }
}

/** Root layout wrapping the entire application with providers, fonts, and user context. */
export default async function RootLayout({
  // Layouts must accept a children prop.
  // This will be populated with nested layouts or pages
  children,
}: {
  children: React.ReactNode
}) {
  const headersList = await headers()
  const nonce = headersList.get('x-nonce') ?? undefined

  const api = await getServerSideAPI()

  let authenticatedUser: schemas['UserRead'] | undefined = undefined
  let userWorkspaces: schemas['Workspace'][] = []

  try {
    authenticatedUser = await getAuthenticatedUser()
    userWorkspaces = await getWorkspaceMemberships(api)
  } catch (e) {
    // Silently swallow errors during build, typically when rendering static pages

    if (process.env.NEXT_PHASE !== PHASE_PRODUCTION_BUILD) {
      throw e
    }
  }

  const distinctId = await getDistinctId()

  return (
    <html
      lang="en"
      suppressHydrationWarning
      className={`antialiased ${GeistSans.variable} ${GeistMono.variable}`}
    >
      <head>
        {/* Theme detection — runs before React hydration to prevent FOUC.
            Nonce is required for CSP ('strict-dynamic'). Browsers strip the
            nonce attribute after execution, so suppressHydrationWarning
            silences the expected server/client mismatch. */}
        <script
          suppressHydrationWarning
          nonce={nonce}
          dangerouslySetInnerHTML={{
            __html:
              '(function(){try{var d=document.documentElement,t=localStorage.getItem("theme"),s=window.matchMedia("(prefers-color-scheme: dark)").matches;if(t==="dark"||(t!=="light"&&s)){d.classList.add("dark");d.style.colorScheme="dark"}else{d.style.colorScheme="light"}}catch(e){}})();',
          }}
        />
        {/* Prevent browser from opening dropped files before React hydrates */}
        <script
          suppressHydrationWarning
          nonce={nonce}
          dangerouslySetInnerHTML={{
            __html:
              '(function(){var d=window.__rapidlyDrop={ready:false,files:null};window.addEventListener("dragover",function(e){e.preventDefault();if(e.dataTransfer)e.dataTransfer.dropEffect="copy"});window.addEventListener("drop",function(e){e.preventDefault();if(!d.ready&&e.dataTransfer&&e.dataTransfer.files.length>0){d.files=Array.from(e.dataTransfer.files);setTimeout(function(){d.files=null},10000)}})})();',
          }}
        />
        <link
          rel="apple-touch-icon"
          sizes="180x180"
          href="/apple-touch-icon.png"
        />
        {/* Google Search uses this — no media query so the crawler always finds it */}
        <link
          rel="icon"
          type="image/png"
          sizes="192x192"
          href="/android-chrome-192x192.png"
        />
        <link rel="manifest" href="/site.webmanifest" />
        <meta
          name="theme-color"
          content="#059669"
          media="(prefers-color-scheme: light)"
        />
        <meta
          name="theme-color"
          content="#0f172a"
          media="(prefers-color-scheme: dark)"
        />
        {CONFIG.ENVIRONMENT === 'development' ? (
          <>
            <link
              href="/favicon-dev.png"
              rel="icon"
              type="image/png"
              sizes="256x256"
              media="(prefers-color-scheme: dark)"
            />
            <link
              href="/favicon-dev-dark.png"
              rel="icon"
              type="image/png"
              sizes="256x256"
              media="(prefers-color-scheme: light)"
            />
          </>
        ) : (
          <>
            <link
              href="/favicon.svg"
              rel="icon"
              type="image/svg+xml"
              media="(prefers-color-scheme: dark)"
            />
            <link
              href="/favicon-dark.svg"
              rel="icon"
              type="image/svg+xml"
              media="(prefers-color-scheme: light)"
            />
            <link
              href="/favicon.png"
              rel="icon"
              type="image/png"
              sizes="256x256"
              media="(prefers-color-scheme: dark)"
            />
            <link
              href="/favicon-dark.png"
              rel="icon"
              type="image/png"
              sizes="256x256"
              media="(prefers-color-scheme: light)"
            />
          </>
        )}
      </head>
      <body
        style={{
          textRendering: 'optimizeLegibility',
        }}
      >
        <QueryProvider>
          <URLStateProvider>
            <UserContextProvider
              user={authenticatedUser}
              userWorkspaces={userWorkspaces}
            >
              <AnalyticsProvider distinctId={distinctId}>
                <SandboxBanner />
                {children}
              </AnalyticsProvider>
            </UserContextProvider>
          </URLStateProvider>
        </QueryProvider>
      </body>
    </html>
  )
}
