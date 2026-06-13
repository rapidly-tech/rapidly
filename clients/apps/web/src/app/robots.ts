import { CONFIG } from '@/utils/config'
import { MetadataRoute } from 'next'

// Per-session ephemeral URLs. The remaining chamber has a
// ``/<chamber>/<slug>`` guest route whose slug expires with the Redis
// channel TTL; indexing it just parks soon-to-404 entries in the
// search index (and leaks session slugs into crawler logs). The
// chamber host page itself (``/secret``) remains indexable — that is
// the "Start a session" landing.
export const DISALLOWED_PATHS = [
  '/dashboard/',
  '/login/',
  '/verify-email/',
  '/file-sharing/',
  // Internal dev harnesses. The pages themselves carry
  // ``robots: {index: false}`` metadata; this is defence-in-depth so
  // crawlers skip the prefix entirely.
  '/dev/',
]

const ALL_AGENTS = '*'

const sandboxRules: MetadataRoute.Robots = {
  rules: { userAgent: ALL_AGENTS, disallow: '/' },
}

const productionRules: MetadataRoute.Robots = {
  rules: {
    userAgent: ALL_AGENTS,
    allow: '/',
    disallow: DISALLOWED_PATHS,
  },
  sitemap: CONFIG.SITEMAP_URL,
}

export default function robots(): MetadataRoute.Robots {
  return CONFIG.IS_SANDBOX ? sandboxRules : productionRules
}
