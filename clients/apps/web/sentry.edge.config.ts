/**
 * Rapidly — Sentry initialisation for edge features (middleware, edge routes).
 * Loaded automatically by Next.js whenever an edge function is invoked.
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
