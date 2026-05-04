/**
 * Pure helpers describing the offline-shell caching strategy.
 *
 * The actual service worker lives at ``public/sw-collab.js`` as
 * plain JavaScript — SWs run in a different bundle context and can't
 * import from ``src``. Instead we keep the strategy in this TS
 * module, mirror its logic in the JS file, and cover the strategy
 * with unit tests here. The JS file has a one-line comment pointing
 * back to this module so anyone editing it knows to re-align.
 *
 * Strategy
 * --------
 * - **HTML navigations** → network-first (``shouldServeNetworkFirst``).
 *   We always try the network so deploys show up instantly; if the
 *   network fails (offline, flaky link) we fall back to the cached
 *   shell. ``/_next/`` and static asset URLs are excluded.
 * - **Hashed static assets** (``/_next/static/…``, ``/icon-*.png``, …)
 *   → cache-first (``shouldServeCacheFirst``). Content-addressed URLs
 *   are immutable — once cached they're valid forever for that
 *   version, and the cache version bump on deploy invalidates the
 *   old set.
 * - **Everything else** — **network-only** (no caching). API calls,
 *   signaling WebSocket upgrades, TURN / STUN traffic all flow
 *   straight through.
 *
 * Cache versioning
 * ----------------
 * ``CACHE_NAME`` carries a version suffix; ``expiredCaches`` returns
 * the names that an ``activate`` handler should delete. Bump the
 * version whenever the precache list changes — old caches disappear,
 * the new one is populated on next ``install``.
 */

/** Bump this on every meaningful change to the precache list. Every
 *  other cache version starting with ``COLLAB_CACHE_PREFIX`` is
 *  considered stale and gets deleted on activate. */
export const COLLAB_CACHE_PREFIX = 'rapidly-collab-shell-'
export const COLLAB_CACHE_VERSION = 'v1'
export const CACHE_NAME = `${COLLAB_CACHE_PREFIX}${COLLAB_CACHE_VERSION}`

/** URLs the shell precaches on install so the canvas page comes up
 *  offline even on the first visit after install. Absolute paths
 *  only; relative URLs resolve against the SW's origin. */
export const PRECACHE_URLS: readonly string[] = [
  '/',
  '/icon-192.png',
  '/icon-512.png',
  '/favicon.svg',
  '/site.webmanifest',
]

/** Network-first only fires for HTML navigations. Pretty URLs and the
 *  root all qualify; anything under ``/_next/`` or an obvious static
 *  extension does not. */
export function shouldServeNetworkFirst(
  url: string,
  destination: string | undefined,
): boolean {
  if (destination === 'document') return true
  // Fallback: accept-type heuristic for callers that don't surface
  // ``destination``. Only HTML-looking paths qualify.
  try {
    const parsed = new URL(url)
    if (parsed.pathname.startsWith('/_next/')) return false
    if (
      /\.(js|css|png|jpg|jpeg|svg|webmanifest|ico|woff2?)$/i.test(
        parsed.pathname,
      )
    ) {
      return false
    }
    return true
  } catch {
    return false
  }
}

/** Cache-first covers hashed static assets — the ``/_next/static/``
 *  tree and the asset-prefixed icon / favicon set. Anything
 *  fingerprinted is immutable for its cache version. */
export function shouldServeCacheFirst(url: string): boolean {
  try {
    const parsed = new URL(url)
    if (parsed.pathname.startsWith('/_next/static/')) return true
    if (/\.(png|jpg|jpeg|svg|webmanifest|ico|woff2?)$/i.test(parsed.pathname)) {
      return true
    }
    return false
  } catch {
    return false
  }
}

/** Given the current set of cache names in ``caches.keys()``, return
 *  the subset that should be deleted on ``activate``. Anything with
 *  our prefix but a different version is stale; anything without our
 *  prefix belongs to a different module (e.g. StreamSaver) and is
 *  left alone. */
export function expiredCaches(
  existing: readonly string[],
  currentVersion: string = COLLAB_CACHE_VERSION,
): string[] {
  const keep = `${COLLAB_CACHE_PREFIX}${currentVersion}`
  return existing.filter(
    (name) => name.startsWith(COLLAB_CACHE_PREFIX) && name !== keep,
  )
}
