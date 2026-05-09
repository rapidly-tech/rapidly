const CONSENT_COOKIE = 'rapidly_cookie_consent'
const CONSENT_MAX_AGE = 60 * 60 * 24 * 365 // 1 year

export function hasConsentCookie(): boolean {
  return document.cookie
    .split(';')
    .some((c) => c.trim().startsWith(`${CONSENT_COOKIE}=`))
}

export function setConsentCookie(value: 'accepted' | 'declined'): void {
  const secure =
    typeof window !== 'undefined' && window.location.protocol === 'https:'
  document.cookie = `${CONSENT_COOKIE}=${value}; path=/; max-age=${CONSENT_MAX_AGE}; samesite=lax${secure ? '; secure' : ''}`
}
