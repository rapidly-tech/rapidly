/**
 * Rapidly — Sentry initialisation for the Node.js server runtime.
 * Loaded for every server-side request (SSR, API routes, server actions).
 * @see https://docs.sentry.io/platforms/javascript/guides/nextjs/
 */

import { CONFIG } from '@/utils/config'
import * as Sentry from '@sentry/nextjs'

Sentry.init({
  dsn: CONFIG.SENTRY_DSN,
  environment: CONFIG.ENVIRONMENT,
  tracesSampleRate: 0.1,
  debug: false,
})
