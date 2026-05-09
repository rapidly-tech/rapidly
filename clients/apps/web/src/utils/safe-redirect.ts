/** Stripe origins that are safe to redirect users to. */
export const ALLOWED_STRIPE_ORIGINS = [
  'https://connect.stripe.com',
  'https://checkout.stripe.com',
  'https://dashboard.stripe.com',
]

/**
 * Validates that a URL is safe to redirect to, preventing open redirect attacks.
 *
 * Only allows same-origin URLs and explicitly allowed external origins
 * (e.g. Stripe checkout).
 */
export function isSafeRedirect(
  url: string,
  allowedOrigins: string[] = [],
): boolean {
  try {
    const parsed = new URL(url, window.location.origin)
    if (parsed.origin === window.location.origin) return true
    return allowedOrigins.includes(parsed.origin)
  } catch {
    return false
  }
}
