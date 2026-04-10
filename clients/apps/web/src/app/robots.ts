import { CONFIG } from '@/utils/config'
import { MetadataRoute } from 'next'

const DISALLOWED_PATHS = [
  '/dashboard/',
  '/login/',
  '/verify-email/',
  '/file-sharing/',
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
