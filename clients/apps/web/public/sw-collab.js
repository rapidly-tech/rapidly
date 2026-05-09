// Rapidly — offline-shell service worker for the Collab chamber.
//
// Strategy + precache list are specified in TypeScript at
// ``src/utils/collab/sw-shell.ts`` and mirrored here because SWs run
// in their own bundle context and can't import from ``src`` at
// runtime. When editing this file, re-align with that module and its
// test suite (``sw-shell.test.ts``) — the TS tests are the source of
// truth for the URL → strategy decisions.
//
// Coexistence: StreamSaver's SW lives at ``/sw.js`` and owns file-
// download piping for the file-sharing chamber. This SW lives at a
// different path + uses a distinct cache-name prefix so the two
// never interfere.

/* global self caches fetch */

const CACHE_PREFIX = 'rapidly-collab-shell-'
const CACHE_VERSION = 'v1'
const CACHE_NAME = CACHE_PREFIX + CACHE_VERSION

// Mirrors PRECACHE_URLS in sw-shell.ts.
const PRECACHE_URLS = [
  '/',
  '/icon-192.png',
  '/icon-512.png',
  '/favicon.svg',
  '/site.webmanifest',
]

self.addEventListener('install', (event) => {
  // Skip waiting so a new SW takes over on first refresh after
  // install rather than requiring two refreshes to activate. Paired
  // with cache versioning so we never serve mixed-version chunks.
  self.skipWaiting()
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) =>
      // ``addAll`` fails loudly if any URL 404s — we'd rather know
      // about a broken precache than limp along with a half-populated
      // cache. Swallow here so a transient deploy glitch doesn't
      // block the SW from activating; the runtime fetch handler will
      // still populate lazily.
      cache.addAll(PRECACHE_URLS).catch(() => undefined),
    ),
  )
})

self.addEventListener('activate', (event) => {
  event.waitUntil(
    (async () => {
      const keys = await caches.keys()
      // Drop every cache that looks like ours but isn't the current
      // version. Non-collab caches (StreamSaver, anyone else) stay.
      await Promise.all(
        keys
          .filter((n) => n.startsWith(CACHE_PREFIX) && n !== CACHE_NAME)
          .map((n) => caches.delete(n)),
      )
      await self.clients.claim()
    })(),
  )
})

self.addEventListener('fetch', (event) => {
  const req = event.request
  // Non-GET flows straight through. Caching a POST would be both
  // incorrect and a potential data-loss hazard.
  if (req.method !== 'GET') return

  const url = req.url

  // HTML navigations → network-first with shell fallback.
  if (shouldServeNetworkFirst(url, req.destination)) {
    event.respondWith(networkFirst(req))
    return
  }

  // Hashed static assets → cache-first.
  if (shouldServeCacheFirst(url)) {
    event.respondWith(cacheFirst(req))
    return
  }

  // Everything else (API / signaling / TURN) flows through unchanged.
})

function shouldServeNetworkFirst(url, destination) {
  if (destination === 'document') return true
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

function shouldServeCacheFirst(url) {
  try {
    const parsed = new URL(url)
    if (parsed.pathname.startsWith('/_next/static/')) return true
    if (
      /\.(png|jpg|jpeg|svg|webmanifest|ico|woff2?)$/i.test(parsed.pathname)
    ) {
      return true
    }
    return false
  } catch {
    return false
  }
}

async function networkFirst(req) {
  try {
    const res = await fetch(req)
    // Only cache successful responses — no point caching a 5xx that
    // might flip back to 200 on the next try.
    if (res.ok) {
      const cache = await caches.open(CACHE_NAME)
      cache.put(req, res.clone())
    }
    return res
  } catch {
    const cached = await caches.match(req)
    if (cached) return cached
    // Last-resort fallback: the cached root shell. Lets the SPA boot
    // even when the requested pretty URL wasn't precached.
    const rootFallback = await caches.match('/')
    if (rootFallback) return rootFallback
    return new Response('Offline', { status: 503, statusText: 'Offline' })
  }
}

async function cacheFirst(req) {
  const cached = await caches.match(req)
  if (cached) return cached
  try {
    const res = await fetch(req)
    if (res.ok) {
      const cache = await caches.open(CACHE_NAME)
      cache.put(req, res.clone())
    }
    return res
  } catch {
    return new Response('Asset unavailable offline', {
      status: 503,
      statusText: 'Offline',
    })
  }
}
