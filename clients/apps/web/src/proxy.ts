import { schemas } from '@rapidly-tech/client'
import crypto from 'crypto'
import { nanoid } from 'nanoid'
import { RequestCookiesAdapter } from 'next/dist/server/web/spec-extension/adapters/request-cookies'
import type { NextRequest } from 'next/server'
import { NextResponse } from 'next/server'
import { buildServerAPI } from './utils/client'
import { ROUTES } from './utils/routes'

const RAPIDLY_AUTH_COOKIE_KEY =
  process.env.RAPIDLY_AUTH_COOKIE_KEY || 'rapidly_session'

const DISTINCT_ID_COOKIE = 'rapidly_distinct_id'
const DISTINCT_ID_COOKIE_MAX_AGE = 60 * 60 * 24 * 365 // 1 year

const AUTHENTICATED_ROUTES = [
  new RegExp('^/start(/.*)?'),
  new RegExp('^/dashboard(/.*)?'),
  new RegExp('^/finance(/.*)?'),
  new RegExp('^/settings(/.*)?'),
  new RegExp('^/oauth2(/.*)?'),
]

const getOrCreateDistinctId = (
  request: NextRequest,
): { id: string; isNew: boolean } => {
  const existing = request.cookies.get(DISTINCT_ID_COOKIE)?.value
  if (existing) {
    return { id: existing, isNew: false }
  }
  return { id: `anon_${nanoid()}`, isNew: true }
}

const isForwardedRoute = (request: NextRequest): boolean => {
  if (request.nextUrl.pathname.startsWith('/docs/')) {
    return true
  }

  if (request.nextUrl.pathname.startsWith('/mintlify-assets/')) {
    return true
  }

  if (request.nextUrl.pathname.startsWith('/_mintlify/')) {
    return true
  }

  if (request.nextUrl.pathname.startsWith('/ingest/')) {
    return true
  }

  return false
}

const requiresAuthentication = (request: NextRequest): boolean => {
  if (isForwardedRoute(request)) {
    return false
  }

  return AUTHENTICATED_ROUTES.some((route) =>
    route.test(request.nextUrl.pathname),
  )
}

const getLoginResponse = (request: NextRequest): NextResponse => {
  const redirectURL = request.nextUrl.clone()
  redirectURL.pathname = ROUTES.LOGIN
  redirectURL.search = ''
  const returnTo = `${request.nextUrl.pathname}${request.nextUrl.search}`
  redirectURL.searchParams.set('return_to', returnTo)
  return NextResponse.redirect(redirectURL)
}

export async function proxy(request: NextRequest) {
  // Do not run middleware for forwarded routes
  // @pieterbeulque added this because the `config.matcher` behavior below
  // doesn't appear to be working consistently with Vercel rewrites
  if (isForwardedRoute(request)) {
    return NextResponse.next()
  }

  // Redirect old customer query string URLs to path-based URLs
  const customersMatch = request.nextUrl.pathname.match(
    /^\/dashboard\/([^/]+)\/customers$/,
  )
  if (customersMatch && request.nextUrl.searchParams.has('customerId')) {
    const customerId = request.nextUrl.searchParams.get('customerId')
    const redirectURL = request.nextUrl.clone()
    redirectURL.pathname = `/dashboard/${customersMatch[1]}/customers/${customerId}`
    redirectURL.searchParams.delete('customerId')
    return NextResponse.redirect(redirectURL)
  }

  let user: schemas['UserRead'] | undefined = undefined

  if (request.cookies.has(RAPIDLY_AUTH_COOKIE_KEY)) {
    const api = await buildServerAPI(
      request.headers,
      RequestCookiesAdapter.seal(request.cookies),
    )
    const { data, response } = await api.GET('/api/users/me', {
      cache: 'no-cache',
    })
    if (!response.ok && response.status !== 401) {
      throw new Error(
        'Unexpected response status while fetching authenticated user',
      )
    }
    user = data
  }

  if (requiresAuthentication(request) && !user) {
    return getLoginResponse(request)
  }

  const { id: distinctId, isNew: isNewDistinctId } =
    getOrCreateDistinctId(request)

  const isImpersonating =
    request.cookies.get('rapidly_is_impersonating')?.value === 'true'

  // Generate CSP nonce for inline scripts
  const nonce = crypto.randomBytes(16).toString('base64')

  const headers: Record<string, string> = {
    'x-nonce': nonce,
    'x-rapidly-distinct-id': distinctId,
    // Always set this header to prevent spoofing via injected request headers.
    // When no user is authenticated, the empty string ensures downstream
    // handlers cannot read a forged value from the original request.
    'x-rapidly-user': user
      ? JSON.stringify({
          id: user.id,
          avatar_url: user.avatar_url,
        })
      : '',
    // Server-side impersonation detection (cookie is httpOnly, so we relay
    // the flag via a request header for downstream server components).
    'x-rapidly-impersonating': isImpersonating ? '1' : '',
  }

  const response = NextResponse.next({ headers })

  // Set dynamic CSP with nonce for routes that use the base policy.
  // File-sharing, download, oauth2, and docs routes keep their own
  // strict static CSPs defined in next.config.mjs.
  const pathname = request.nextUrl.pathname
  const hasOwnCSP =
    pathname.startsWith('/oauth2') ||
    pathname.startsWith('/docs') ||
    pathname.startsWith('/download') ||
    pathname.startsWith('/file-sharing') ||
    pathname === '/stream.html'

  if (!hasOwnCSP) {
    const apiUrl = process.env.NEXT_PUBLIC_API_URL || ''
    const apiWsUrl = apiUrl.replace(/^http/, 'ws')
    const s3Origins = process.env.S3_UPLOAD_ORIGINS || ''
    const csp = [
      `default-src 'self'`,
      `connect-src 'self' ${apiUrl} ${apiWsUrl} ${s3Origins} https://api.stripe.com https://maps.googleapis.com https://*.google-analytics.com https://chat.uk.plain.com`,
      `frame-src 'self' https://*.js.stripe.com https://js.stripe.com https://hooks.stripe.com https://customer-wl21dabnj6qtvcai.cloudflarestream.com videodelivery.net *.cloudflarestream.com`,
      `script-src 'self' 'unsafe-inline' ${process.env.NODE_ENV === 'development' ? "'unsafe-eval'" : ''} https://*.js.stripe.com https://js.stripe.com https://maps.googleapis.com https://www.googletagmanager.com https://chat.cdn-plain.com https://embed.cloudflarestream.com`,
      `style-src 'self' 'unsafe-inline' https://fonts.googleapis.com`,
      `img-src 'self' blob: data: https://www.gravatar.com https://img.logo.dev https://lh3.googleusercontent.com https://avatars.githubusercontent.com https://uploads.rapidly.tech https://i0.wp.com`,
      `font-src 'self'`,
      `object-src 'none'`,
      `base-uri 'self'`,
      `form-action 'self' ${apiUrl}`,
      `frame-ancestors 'none'`,
      process.env.NODE_ENV === 'production' ? 'upgrade-insecure-requests' : '',
    ]
      .filter(Boolean)
      .join('; ')

    response.headers.set('Content-Security-Policy', csp)
  }

  // Only persist the distinct ID cookie when the user has given consent
  // to analytics tracking. Without consent we still generate a transient
  // ID for the request (used in the header) but don't persist it.
  const hasAnalyticsConsent =
    request.cookies.get('rapidly_cookie_consent')?.value === 'accepted'

  if (isNewDistinctId && hasAnalyticsConsent) {
    response.cookies.set(DISTINCT_ID_COOKIE, distinctId, {
      maxAge: DISTINCT_ID_COOKIE_MAX_AGE,
      httpOnly: true,
      secure: process.env.NODE_ENV === 'production',
      sameSite: 'lax',
    })
  }

  return response
}

export const config = {
  matcher: [
    /*
     * Match all request paths except for the ones starting with:
     * - api (API routes)
     * - ingest (Posthog)
     * - monitoring (Sentry)
     * - docs, _mintlify, mintlify-assets (Mintlify)
     * - _next/static (static files)
     * - _next/image (image optimization files)
     * - favicon.ico, sitemap.xml, robots.txt (metadata files)
     */
    '/((?!api|ingest|monitoring|docs|_mintlify|mintlify-assets|_next/static|_next/image|favicon.ico|sitemap.xml|robots.txt).*)',
  ],
}
