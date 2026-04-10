/* global process */
import bundleAnalyzer from '@next/bundle-analyzer'
import createMDX from '@next/mdx'
import { withSentryConfig } from '@sentry/nextjs'
import { themeConfig } from './shiki.config.mjs'

const RAPIDLY_AUTH_COOKIE_KEY =
  process.env.RAPIDLY_AUTH_COOKIE_KEY || 'rapidly_session'
const ENVIRONMENT =
  process.env.RAPIDLY_ENV || process.env.NODE_ENV || 'development'
const CODESPACES = process.env.CODESPACES === 'true'

const defaultFrontendHostname = process.env.NEXT_PUBLIC_FRONTEND_BASE_URL
  ? new URL(process.env.NEXT_PUBLIC_FRONTEND_BASE_URL).hostname
  : 'rapidly.tech'

const S3_PUBLIC_IMAGES_BUCKET_ORIGIN = process.env
  .S3_PUBLIC_IMAGES_BUCKET_HOSTNAME
  ? `${process.env.S3_PUBLIC_IMAGES_BUCKET_PROTOCOL || 'https'}://${process.env.S3_PUBLIC_IMAGES_BUCKET_HOSTNAME}${process.env.S3_PUBLIC_IMAGES_BUCKET_PORT ? `:${process.env.S3_PUBLIC_IMAGES_BUCKET_PORT}` : ''}`
  : ''
// WebSocket URL for signaling (derive wss: from API URL or use 'self' for same-origin)
const apiWsUrl = (process.env.NEXT_PUBLIC_API_URL || '').replace(/^http/, 'ws')

const baseCSP = `
    default-src 'self';
    connect-src 'self' ${process.env.NEXT_PUBLIC_API_URL || ''} ${apiWsUrl} ${process.env.S3_UPLOAD_ORIGINS || ''} https://api.stripe.com https://maps.googleapis.com https://*.google-analytics.com https://chat.uk.plain.com;
    frame-src 'self' https://*.js.stripe.com https://js.stripe.com https://hooks.stripe.com https://customer-wl21dabnj6qtvcai.cloudflarestream.com videodelivery.net *.cloudflarestream.com;
    script-src 'self' 'unsafe-eval' 'unsafe-inline' https://*.js.stripe.com https://js.stripe.com https://maps.googleapis.com https://www.googletagmanager.com https://chat.cdn-plain.com https://embed.cloudflarestream.com;
    style-src 'self' 'unsafe-inline' https://fonts.googleapis.com;
    img-src 'self' blob: data: https://www.gravatar.com https://img.logo.dev https://lh3.googleusercontent.com https://avatars.githubusercontent.com ${S3_PUBLIC_IMAGES_BUCKET_ORIGIN} https://uploads.rapidly.tech https://i0.wp.com;
    font-src 'self';
    object-src 'none';
    base-uri 'self';
    ${ENVIRONMENT !== 'development' ? 'upgrade-insecure-requests;' : ''}
`
// nonEmbeddedCSP was replaced by dynamic CSP in proxy.ts (middleware).
// Kept as reference for the directives included in the dynamic policy.
const _nonEmbeddedCSP = `
  ${baseCSP}
  form-action 'self' ${process.env.NEXT_PUBLIC_API_URL};
  frame-ancestors 'none';
`
// Don't add form-action to the OAuth2 authorize page, as it blocks the OAuth2 redirection
// 10-years old debate about whether to block redirects with form-action or not: https://github.com/w3c/webappsec-csp/issues/8
const oauth2CSP = `
  ${baseCSP}
  frame-ancestors 'none';
`

// We rewrite Mintlify docs to rapidly.tech/docs, so we need a specific CSP for them
// Ref: https://www.mintlify.com/docs/guides/csp-configuration#content-security-policy-csp-configuration
const docsCSP = `
  default-src 'self';
  script-src 'self' 'unsafe-inline' 'unsafe-eval' cdn.jsdelivr.net www.googletagmanager.com cdn.segment.com plausible.io
  us.posthog.com tag.clearbitscripts.com cdn.heapanalytics.com chat.cdn-plain.com chat-assets.frontapp.com
  browser.sentry-cdn.com js.sentry-cdn.com;
  style-src 'self' 'unsafe-inline' d4tuoctqmanu0.cloudfront.net fonts.googleapis.com;
  font-src 'self' d4tuoctqmanu0.cloudfront.net fonts.googleapis.com;
  img-src 'self' data: blob: d3gk2c5xim1je2.cloudfront.net mintcdn.com *.mintcdn.com cdn.jsdelivr.net mintlify.s3.us-west-1.amazonaws.com;
  connect-src 'self' *.mintlify.dev *.mintlify.com d1ctpt7j8wusba.cloudfront.net mintcdn.com *.mintcdn.com
  api.mintlifytrieve.com www.googletagmanager.com cdn.segment.com plausible.io us.posthog.com browser.sentry-cdn.com;
  frame-src 'self' *.mintlify.dev https://uploads.rapidly.tech;
`

/** @type {import('next').NextConfig} */
const nextConfig = {
  output: 'standalone',
  reactStrictMode: true,
  allowedDevOrigins: ['127.0.0.1', 'localhost'],
  transpilePackages: ['shiki'],
  pageExtensions: ['js', 'jsx', 'md', 'mdx', 'ts', 'tsx'],

  // This is required to support PostHog trailing slash API requests
  skipTrailingSlashRedirect: true,

  // Tree-shake heavy packages for smaller bundles
  experimental: {
    optimizePackageImports: [
      'framer-motion',
      '@iconify/react',
      '@tanstack/react-query',
      'posthog-js',
      'lucide-react',
    ],
  },

  webpack: (config, { dev }) => {
    if (config.cache && !dev) {
      config.cache = Object.freeze({
        type: 'memory',
      })
    }

    return config
  },

  // Since Codespaces run behind a proxy, we need to allow it for Server-Side Actions, like cache revalidation
  // See: https://github.com/vercel/next.js/issues/58019
  ...(CODESPACES
    ? {
        experimental: {
          serverActions: {
            allowedForwardedHosts: [
              `${process.env.CODESPACE_NAME}-8080.${process.env.GITHUB_CODESPACES_PORT_FORWARDING_DOMAIN}`,
              'localhost:8080',
              '127.0.0.1:8080',
            ],
            allowedOrigins: [
              `${process.env.CODESPACE_NAME}-8080.${process.env.GITHUB_CODESPACES_PORT_FORWARDING_DOMAIN}`,
              'localhost:8080',
              '127.0.0.1:8080',
            ],
          },
        },
      }
    : {}),

  images: {
    remotePatterns: [
      ...(process.env.S3_PUBLIC_IMAGES_BUCKET_HOSTNAME
        ? [
            {
              protocol: process.env.S3_PUBLIC_IMAGES_BUCKET_PROTOCOL || 'https',
              hostname: process.env.S3_PUBLIC_IMAGES_BUCKET_HOSTNAME,
              port: process.env.S3_PUBLIC_IMAGES_BUCKET_PORT || '',
              pathname: process.env.S3_PUBLIC_IMAGES_BUCKET_PATHNAME || '**',
            },
          ]
        : []),
      {
        protocol: 'https',
        hostname: 'avatars.githubusercontent.com',
        port: '',
        pathname: '**',
      },
      {
        protocol: 'https',
        hostname: 'uploads.rapidly.tech',
        port: '',
        pathname: '**',
      },
    ],
  },

  async rewrites() {
    return [
      {
        source: '/ingest/static/:path*',
        destination: 'https://us-assets.i.posthog.com/static/:path*',
      },
      {
        source: '/ingest/:path*',
        destination: 'https://us.i.posthog.com/:path*',
      },
      {
        source: '/ingest/decide',
        destination: 'https://us.i.posthog.com/decide',
      },
      // File sharing API rewrites (includes secret sharing and WebSocket signaling)
      {
        source: '/api/file-sharing/:path*',
        destination: `${process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000'}/api/file-sharing/:path*`,
      },
      // Mintlify docs rewrite
      {
        source: '/docs/:path*',
        destination: 'https://docs.rapidly.tech/:path*',
      },
    ]
  },

  async redirects() {
    return [
      // dashboard.rapidly.tech redirections
      {
        source: '/',
        destination: '/login',
        has: [
          {
            type: 'host',
            value: 'dashboard.rapidly.tech',
          },
        ],
        permanent: false,
      },
      {
        source: '/:path*',
        destination: 'https://rapidly.tech/:path*',
        has: [
          {
            type: 'host',
            value: 'dashboard.rapidly.tech',
          },
        ],
        permanent: false,
      },
      {
        source: '/careers',
        destination: 'https://rapidly.tech/about',
        permanent: false,
      },
      {
        source: '/llms.txt',
        destination: 'https://rapidly.tech/docs/llms.txt',
        permanent: true,
        has: [
          {
            type: 'host',
            value: 'rapidly.tech',
          },
        ],
      },
      {
        source: '/llms-full.txt',
        destination: 'https://rapidly.tech/docs/llms-full.txt',
        permanent: true,
        has: [
          {
            type: 'host',
            value: 'rapidly.tech',
          },
        ],
      },

      // Logged-in user redirections
      {
        source: '/',
        destination: '/start',
        has: [
          {
            type: 'cookie',
            key: RAPIDLY_AUTH_COOKIE_KEY,
          },
          {
            type: 'host',
            value: defaultFrontendHostname,
          },
        ],
        permanent: false,
      },

      // Redirect /maintainer to rapidly.tech if on a different domain name
      {
        source: '/dashboard/:path*',
        destination: `https://${defaultFrontendHostname}/dashboard/:path*`,
        missing: [
          {
            type: 'host',
            value: defaultFrontendHostname,
          },
          {
            type: 'header',
            key: 'x-forwarded-host',
            value: defaultFrontendHostname,
          },
        ],
        permanent: false,
      },

      {
        source: '/maintainer',
        destination: '/dashboard',
        permanent: true,
      },
      {
        source: '/maintainer/:path(.*)',
        destination: '/dashboard/:path(.*)',
        permanent: true,
      },
      {
        source: '/finance',
        destination: '/finance/income',
        permanent: false,
      },
      {
        source: '/dashboard/:organization/overview',
        destination: '/dashboard/:organization',
        permanent: true,
      },
      {
        source: '/dashboard/:organization/benefits',
        destination: '/dashboard/:organization/shares/benefits',
        permanent: true,
      },
      {
        source: '/dashboard/:organization/products/overview',
        destination: '/dashboard/:organization/shares',
        permanent: true,
      },
      {
        source: '/dashboard/:organization/issues',
        destination: '/dashboard/:organization/issues/overview',
        permanent: false,
      },
      {
        source: '/dashboard/:organization/promote/issues',
        destination: '/dashboard/:organization/issues/badge',
        permanent: false,
      },
      {
        source: '/dashboard/:organization/issues/promote',
        destination: '/dashboard/:organization/issues/badge',
        permanent: false,
      },
      {
        source: '/dashboard/:organization/finance',
        destination: '/dashboard/:organization/finance/income',
        permanent: false,
      },
      {
        source: '/dashboard/:organization/usage-billing',
        destination: '/dashboard/:organization/shares/meters',
        permanent: true,
      },
      {
        source: '/dashboard/:organization/usage-billing/meters',
        destination: '/dashboard/:organization/shares/meters',
        permanent: true,
      },
      {
        source: '/dashboard/:organization/usage-billing/events',
        destination: '/dashboard/:organization/analytics/events',
        permanent: true,
      },
      {
        source: '/dashboard/:organization/usage-billing/spans',
        destination: '/dashboard/:organization/analytics/costs',
        permanent: true,
      },

      // Old onboarding URLs → Dashboard
      {
        source: '/dashboard/:organization/onboarding/product',
        destination: '/dashboard/:organization',
        permanent: true,
      },
      {
        source: '/dashboard/:organization/onboarding/integrate',
        destination: '/dashboard/:organization',
        permanent: true,
      },

      // File Sharing → Shares/Send Files
      {
        source: '/dashboard/:organization/file-sharing',
        destination: '/dashboard/:organization/shares/send-files',
        permanent: true,
      },

      // Products → Shares Redirects
      {
        source: '/dashboard/:organization/products',
        destination: '/dashboard/:organization/shares',
        permanent: true,
      },
      {
        source: '/dashboard/:organization/products/:path*',
        destination: '/dashboard/:organization/shares/:path*',
        permanent: true,
      },
      {
        source: '/:organization/products/:path*',
        destination: '/:organization/shares/:path*',
        permanent: true,
      },

      // Account Settings Redirects
      {
        source: '/settings',
        destination: '/dashboard/account/preferences',
        permanent: true,
      },

      // Access tokens redirect
      {
        source: '/settings/tokens',
        destination: '/account/developer',
        permanent: false,
      },

      // Old blog redirects
      {
        source: '/rapidly-tech/posts',
        destination: '/blog',
        permanent: false,
      },
      {
        source: '/rapidly-tech/posts/:path(.*)',
        destination: '/blog/:path*',
        permanent: false,
      },

      // Fallback blog redirect
      {
        source: '/:path*',
        destination: 'https://rapidly.tech/rapidly-tech',
        has: [
          {
            type: 'host',
            value: 'blog.rapidly.tech',
          },
        ],
        permanent: false,
      },
    ]
  },
  async headers() {
    const baseHeaders = [
      // CSP for base routes is set dynamically in middleware (proxy.ts)
      // with a per-request nonce. Only file-sharing, download, oauth2,
      // and docs routes use static CSP from this config.
      {
        key: 'Strict-Transport-Security',
        value: 'max-age=63072000; includeSubDomains; preload',
      },
      {
        key: 'X-Content-Type-Options',
        value: 'nosniff',
      },
      {
        key: 'Referrer-Policy',
        value: 'strict-origin-when-cross-origin',
      },
      {
        key: 'Permissions-Policy',
        value:
          'payment=(), publickey-credentials-get=(), camera=(), microphone=(), geolocation=(), accelerometer=(), gyroscope=(), magnetometer=(), usb=()',
      },
      {
        key: 'X-Frame-Options',
        value: 'DENY',
      },
      // Cross-Origin isolation headers for enhanced security
      {
        key: 'Cross-Origin-Opener-Policy',
        value: 'same-origin',
      },
      // COEP credentialless: provides Spectre/Meltdown isolation without breaking
      // cross-origin resources that don't send CORP headers (e.g. Stripe, GTM)
      {
        key: 'Cross-Origin-Embedder-Policy',
        value: 'credentialless',
      },
      {
        key: 'Cross-Origin-Resource-Policy',
        value: 'cross-origin',
      },
      {
        key: 'X-DNS-Prefetch-Control',
        value: 'off',
      },
      {
        key: 'X-Download-Options',
        value: 'noopen',
      },
    ]

    // Add X-Robots-Tag header for sandbox environment
    if (ENVIRONMENT === 'sandbox') {
      baseHeaders.push({
        key: 'X-Robots-Tag',
        value: 'noindex, nofollow, noarchive, nosnippet, noimageindex',
      })
    }

    // Base CSP for file-sharing upload page (/file-sharing)
    // Significantly tighter than base: NO unsafe-eval or unsafe-inline in script-src
    // These routes only need the API, WebSocket signaling, and StreamSaver — no Stripe/GTM/Maps
    const fileSharingBaseCSP = `
      default-src 'self';
      connect-src 'self' ${process.env.NEXT_PUBLIC_API_URL || ''} ${apiWsUrl};
      frame-src 'none';
      frame-ancestors 'none';
      form-action 'self';
      script-src 'self';
      style-src 'self' 'unsafe-inline';
      img-src 'self' blob: data:;
      font-src 'self';
      object-src 'none';
      base-uri 'self';
      ${ENVIRONMENT !== 'development' ? 'upgrade-insecure-requests;' : ''}
    `

    // CSP for download routes (StreamSaver framing)
    // Defined independently (NOT nesting fileSharingBaseCSP) because CSP does not
    // support overriding directives — the first frame-src wins. StreamSaver.js
    // embeds /stream.html in an iframe, so we need frame-src 'self' here.
    const downloadCSP = `
      default-src 'self';
      connect-src 'self' ${process.env.NEXT_PUBLIC_API_URL || ''} ${apiWsUrl};
      frame-src 'self';
      script-src 'self';
      style-src 'self' 'unsafe-inline';
      img-src 'self' blob: data:;
      font-src 'self';
      object-src 'none';
      base-uri 'self';
      worker-src 'self' blob:;
      form-action 'self';
      frame-ancestors 'self';
      ${ENVIRONMENT !== 'development' ? 'upgrade-insecure-requests;' : ''}
    `

    // CSP for stream.html (StreamSaver MITM page)
    // Needs the inline script hash since we can't modify the third-party script
    const streamHtmlCSP = `
      default-src 'self';
      connect-src 'self';
      frame-src 'none';
      script-src 'self' 'sha256-b3XkKx9p3a3FayeY/TBnyNSRclMfLOYm9Oh9N5t60dI=';
      style-src 'self';
      img-src 'none';
      font-src 'none';
      object-src 'none';
      base-uri 'self';
      worker-src 'self' blob:;
      form-action 'self';
      frame-ancestors 'self';
      ${ENVIRONMENT !== 'development' ? 'upgrade-insecure-requests;' : ''}
    `

    // CSP for the file sharing upload page
    const fileSharingCSP = `
      ${fileSharingBaseCSP}
      worker-src 'self' blob:;
    `

    return [
      {
        source:
          '/((?!oauth2|docs|download|file-sharing|stream.html).*)',
        headers: baseHeaders,
      },
      {
        source: '/download/:path*',
        headers: [
          {
            key: 'Content-Security-Policy',
            value: downloadCSP.replace(/\n/g, ''),
          },
          {
            key: 'Cache-Control',
            value: 'no-store, no-cache, must-revalidate',
          },
          {
            key: 'Strict-Transport-Security',
            value: 'max-age=63072000; includeSubDomains; preload',
          },
          {
            key: 'X-Content-Type-Options',
            value: 'nosniff',
          },
          {
            key: 'Referrer-Policy',
            value: 'no-referrer',
          },
          {
            key: 'Permissions-Policy',
            value:
              'payment=(), publickey-credentials-get=(), camera=(), microphone=(), geolocation=(), accelerometer=(), gyroscope=(), magnetometer=(), usb=()',
          },
          // Enhanced cross-origin isolation for file sharing security
          {
            key: 'Cross-Origin-Opener-Policy',
            value: 'same-origin',
          },
          {
            key: 'Cross-Origin-Embedder-Policy',
            value: 'credentialless',
          },
          {
            key: 'Cross-Origin-Resource-Policy',
            value: 'same-origin',
          },
          {
            // SAMEORIGIN to match CSP frame-ancestors 'self' (needed for StreamSaver MITM iframe)
            key: 'X-Frame-Options',
            value: 'SAMEORIGIN',
          },
          {
            key: 'X-DNS-Prefetch-Control',
            value: 'off',
          },
          {
            key: 'X-Download-Options',
            value: 'noopen',
          },
          ...(ENVIRONMENT === 'sandbox'
            ? [
                {
                  key: 'X-Robots-Tag',
                  value:
                    'noindex, nofollow, noarchive, nosnippet, noimageindex',
                },
              ]
            : []),
        ],
      },
      {
        source: '/file-sharing/:path*',
        headers: [
          {
            key: 'Content-Security-Policy',
            value: fileSharingCSP.replace(/\n/g, ''),
          },
          {
            key: 'Cache-Control',
            value: 'no-store, no-cache, must-revalidate',
          },
          {
            key: 'Strict-Transport-Security',
            value: 'max-age=63072000; includeSubDomains; preload',
          },
          {
            key: 'X-Content-Type-Options',
            value: 'nosniff',
          },
          {
            key: 'Referrer-Policy',
            value: 'no-referrer',
          },
          {
            key: 'Permissions-Policy',
            value:
              'payment=(), publickey-credentials-get=(), camera=(), microphone=(), geolocation=(), accelerometer=(), gyroscope=(), magnetometer=(), usb=()',
          },
          {
            key: 'X-Frame-Options',
            value: 'DENY',
          },
          {
            key: 'Cross-Origin-Opener-Policy',
            value: 'same-origin',
          },
          {
            key: 'Cross-Origin-Embedder-Policy',
            value: 'credentialless',
          },
          {
            key: 'Cross-Origin-Resource-Policy',
            value: 'same-origin',
          },
          {
            key: 'X-DNS-Prefetch-Control',
            value: 'off',
          },
          {
            key: 'X-Download-Options',
            value: 'noopen',
          },
          ...(ENVIRONMENT === 'sandbox'
            ? [
                {
                  key: 'X-Robots-Tag',
                  value:
                    'noindex, nofollow, noarchive, nosnippet, noimageindex',
                },
              ]
            : []),
        ],
      },
      {
        source: '/stream.html',
        headers: [
          {
            key: 'Content-Security-Policy',
            value: streamHtmlCSP.replace(/\n/g, ''),
          },
          {
            key: 'Strict-Transport-Security',
            value: 'max-age=63072000; includeSubDomains; preload',
          },
          {
            key: 'X-Content-Type-Options',
            value: 'nosniff',
          },
          {
            key: 'Cache-Control',
            value: 'no-store',
          },
          {
            key: 'X-Frame-Options',
            value: 'SAMEORIGIN',
          },
          {
            key: 'Referrer-Policy',
            value: 'no-referrer',
          },
          {
            key: 'Permissions-Policy',
            value:
              'payment=(), publickey-credentials-get=(), camera=(), microphone=(), geolocation=(), accelerometer=(), gyroscope=(), magnetometer=(), usb=()',
          },
          // Enhanced cross-origin isolation for streaming downloads
          {
            key: 'Cross-Origin-Opener-Policy',
            value: 'same-origin',
          },
          {
            key: 'Cross-Origin-Embedder-Policy',
            value: 'credentialless',
          },
          {
            key: 'Cross-Origin-Resource-Policy',
            value: 'same-origin',
          },
        ],
      },
      {
        source: '/oauth2/:path*',
        headers: [
          {
            key: 'Content-Security-Policy',
            value: oauth2CSP.replace(/\n/g, ''),
          },
          {
            key: 'Strict-Transport-Security',
            value: 'max-age=63072000; includeSubDomains; preload',
          },
          {
            key: 'X-Content-Type-Options',
            value: 'nosniff',
          },
          {
            key: 'Referrer-Policy',
            value: 'strict-origin-when-cross-origin',
          },
          {
            key: 'Permissions-Policy',
            value:
              'payment=(), publickey-credentials-get=(), camera=(), microphone=(), geolocation=(), accelerometer=(), gyroscope=(), magnetometer=(), usb=()',
          },
          {
            key: 'X-Frame-Options',
            value: 'DENY',
          },
          {
            key: 'Cross-Origin-Opener-Policy',
            value: 'same-origin',
          },
          ...(ENVIRONMENT === 'sandbox'
            ? [
                {
                  key: 'X-Robots-Tag',
                  value:
                    'noindex, nofollow, noarchive, nosnippet, noimageindex',
                },
              ]
            : []),
        ],
      },
      {
        source: '/docs/:path*',
        headers: [
          {
            key: 'Content-Security-Policy',
            value: docsCSP.replace(/\n/g, ''),
          },
          {
            key: 'Strict-Transport-Security',
            value: 'max-age=63072000; includeSubDomains; preload',
          },
          {
            key: 'X-Content-Type-Options',
            value: 'nosniff',
          },
          {
            key: 'Referrer-Policy',
            value: 'strict-origin-when-cross-origin',
          },
          {
            key: 'Permissions-Policy',
            value:
              'payment=(), publickey-credentials-get=(), camera=(), microphone=(), geolocation=(), accelerometer=(), gyroscope=(), magnetometer=(), usb=()',
          },
          {
            key: 'X-Frame-Options',
            value: 'DENY',
          },
          {
            key: 'Cross-Origin-Opener-Policy',
            value: 'same-origin',
          },
          ...(ENVIRONMENT === 'sandbox'
            ? [
                {
                  key: 'X-Robots-Tag',
                  value:
                    'noindex, nofollow, noarchive, nosnippet, noimageindex',
                },
              ]
            : []),
        ],
      },
    ]
  },
}

const createConfig = async () => {
  const withMDX = createMDX({
    options: {
      remarkPlugins: ['remark-frontmatter', 'remark-gfm'],
      rehypePlugins: [
        'rehype-mdx-import-media',
        'rehype-slug',
        [
          '@shikijs/rehype',
          {
            themes: themeConfig,
          },
        ],
      ],
    },
  })

  let conf = withMDX(nextConfig)

  // Injected content via Sentry wizard below

  conf = withSentryConfig(conf, {
    // For all available options, see:
    // https://github.com/getsentry/sentry-webpack-plugin#options

    org: 'rapidly-tech',
    project: 'dashboard',

    // Pass the auth token
    authToken: process.env.SENTRY_AUTH_TOKEN,

    // Only print logs for uploading source maps in CI
    silent: !process.env.CI,

    // For all available options, see:
    // https://docs.sentry.io/platforms/javascript/guides/nextjs/manual-setup/

    // Upload a larger set of source maps for prettier stack traces (increases build time)
    widenClientFileUpload: true,

    reactComponentAnnotation: {
      enabled: false,
    },

    // Route browser requests to Sentry through a Next.js rewrite to circumvent ad-blockers.
    // This can increase your server load as well as your hosting bill.
    // Note: Check that the configured route will not match with your Next.js middleware, otherwise reporting of client-
    // side errors will fail.
    tunnelRoute: '/monitoring',

    // Hides source maps from generated client bundles
    hideSourceMaps: true,

    // Automatically tree-shake Sentry logger statements to reduce bundle size
    disableLogger: true,

    automaticVercelMonitors: false,
  })

  if (process.env.ANALYZE === 'true') {
    const withBundleAnalyzer = bundleAnalyzer({
      enabled: true,
    })
    conf = withBundleAnalyzer(conf)
  }

  return conf
}

export default createConfig
