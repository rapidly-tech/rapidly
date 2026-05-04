/**
 * Rapidly Apple Pay domain verification route.
 *
 * Serves the Apple Developer Merchant ID domain association file at the
 * .well-known path, enabling Apple Pay on the Rapidly checkout domain.
 * Runs on the Edge runtime for low-latency responses.
 *
 * @module rapidly/well-known/apple-developer-merchantid-domain-association
 */
import { CONFIG } from '@/utils/config'

export const runtime = 'edge'

export async function GET() {
  return new Response(CONFIG.APPLE_DOMAIN_ASSOCIATION, {
    status: 200,
  })
}
