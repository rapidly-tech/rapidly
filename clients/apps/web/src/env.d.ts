/** Pre-hydration drag-and-drop buffer (set by inline script in layout.tsx) */
interface EarlyDropBuffer {
  ready: boolean
  files: File[] | null
}

interface Window {
  __rapidlyDrop: EarlyDropBuffer
}

declare namespace NodeJS {
  interface ProcessEnv {
    // Environment
    readonly NEXT_PUBLIC_ENVIRONMENT?: string
    readonly VERCEL_ENV?: string
    readonly NEXT_PUBLIC_VERCEL_ENV?: string

    // URLs
    readonly NEXT_PUBLIC_API_URL?: string
    readonly NEXT_PUBLIC_FRONTEND_BASE_URL?: string
    readonly NEXT_PUBLIC_BACKOFFICE_URL?: string
    readonly NEXT_PUBLIC_LOGIN_PATH?: string
    readonly RAPIDLY_API_URL?: string

    // Auth
    readonly RAPIDLY_AUTH_COOKIE_KEY?: string
    readonly RAPIDLY_AUTH_MCP_COOKIE_KEY?: string

    // Stripe
    readonly NEXT_PUBLIC_STRIPE_KEY?: string

    // Analytics & Monitoring
    readonly NEXT_PUBLIC_GOOGLE_ANALYTICS_ID?: string
    readonly NEXT_PUBLIC_SENTRY_DSN?: string
    readonly SENTRY_AUTH_TOKEN?: string
    readonly NEXT_PUBLIC_POSTHOG_TOKEN?: string

    // Apple Pay
    readonly NEXT_PUBLIC_APPLE_DOMAIN_ASSOCIATION?: string

    // S3/Storage
    readonly S3_PUBLIC_IMAGES_BUCKET_PROTOCOL?: string
    readonly S3_PUBLIC_IMAGES_BUCKET_HOSTNAME?: string
    readonly S3_PUBLIC_IMAGES_BUCKET_PORT?: string
    readonly S3_PUBLIC_IMAGES_BUCKET_PATHNAME?: string
    readonly S3_UPLOAD_ORIGINS?: string

    // AI Services (server-only)
    readonly GOOGLE_GENERATIVE_AI_API_KEY?: string
    readonly ANTHROPIC_API_KEY?: string
    readonly GRAM_API_KEY?: string
    readonly GRAM_API_URL?: string

    // MCP OAuth (server-only)
    readonly MCP_OAUTH2_CLIENT_ID?: string
    readonly MCP_OAUTH2_CLIENT_SECRET?: string

    // Codespaces
    readonly CODESPACES?: string
  }
}
