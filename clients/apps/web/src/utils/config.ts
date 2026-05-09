const defaults = {
  ENVIRONMENT:
    process.env.NEXT_PUBLIC_ENVIRONMENT ||
    process.env.VERCEL_ENV ||
    process.env.NEXT_PUBLIC_VERCEL_ENV ||
    'development',
  FRONTEND_BASE_URL:
    process.env.NEXT_PUBLIC_FRONTEND_BASE_URL || 'http://127.0.0.1:3000',
  BASE_URL: process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000',
  AUTH_COOKIE_KEY: process.env.RAPIDLY_AUTH_COOKIE_KEY || 'rapidly_session',
  AUTH_MCP_COOKIE_KEY:
    process.env.RAPIDLY_AUTH_MCP_COOKIE_KEY || 'rapidly_mcp_session',
  LOGIN_PATH: process.env.NEXT_PUBLIC_LOGIN_PATH || '/login',
  GOOGLE_ANALYTICS_ID: process.env.NEXT_PUBLIC_GOOGLE_ANALYTICS_ID || undefined,
  SENTRY_DSN: process.env.NEXT_PUBLIC_SENTRY_DSN || undefined,
  POSTHOG_TOKEN: process.env.NEXT_PUBLIC_POSTHOG_TOKEN || '',
  APPLE_DOMAIN_ASSOCIATION:
    process.env.NEXT_PUBLIC_APPLE_DOMAIN_ASSOCIATION ||
    '<Replace with Apple Pay Domain Association from Stripe>',
  ADMIN_EMAIL: process.env.NEXT_PUBLIC_ADMIN_EMAIL || '',
}

export const CONFIG = {
  ...defaults,
  IS_SANDBOX: defaults.ENVIRONMENT === 'sandbox',
  SANDBOX_URL: process.env.NEXT_PUBLIC_SANDBOX_URL || '',

  // Derived URLs - use these instead of hardcoding rapidly.tech
  OG_IMAGE_URL: `${defaults.FRONTEND_BASE_URL}/assets/brand/rapidly_og.jpg`,
  OG_POSTS_IMAGE_BASE_URL: `${defaults.FRONTEND_BASE_URL}/assets/posts/og`,
  SITEMAP_URL: `${defaults.FRONTEND_BASE_URL}/sitemap.xml`,
  DOCS_BASE_URL:
    process.env.NEXT_PUBLIC_DOCS_URL || 'https://docs.rapidly.tech',
  LEGAL_TERMS_URL: `${defaults.FRONTEND_BASE_URL}/legal/terms`,
  LEGAL_PRIVACY_URL: `${defaults.FRONTEND_BASE_URL}/legal/privacy`,

  // External services
  POSTHOG_HOST: 'https://us.i.posthog.com',
  DISCORD_WEBHOOK_URL_PREFIX: 'https://discord.com/api/webhooks',
}

/** Generate OG image URL for an workspace */
export const orgOgImageUrl = (orgSlug: string) =>
  `${CONFIG.FRONTEND_BASE_URL}/og?org=${orgSlug}`
