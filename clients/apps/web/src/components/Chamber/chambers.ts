/**
 * Registry of the public product chambers. Used by the chamber-strip nav
 * on the public landing and by per-chamber page metadata.
 *
 * What's gone vs. the original six-chamber product:
 * - Files: file_sharing is kept in code as transport infrastructure
 *   (powers /share/<slug> anonymous-receive), but no longer surfaced as
 *   a top-level chamber.
 * - Screen / Watch / Call: the media chambers were removed entirely.
 * - Markup (ex-Collab): the realtime markup chamber was removed; only its
 *   shared transport/crypto utilities remain in file_sharing.
 *
 * What remains is intentionally small — Secret as a no-account one-time-
 * message surface that maps cleanly to a quick engineering workflow.
 *
 * "live" chambers link to a working route. "soon" chambers render with a
 * muted treatment and surface a "coming soon" pill so visitors learn what
 * is on the roadmap without the disappointment of a 404.
 */

export type ChamberStatus = 'live' | 'soon'

export interface Chamber {
  id: string
  label: string
  /** Iconify icon name (Solar collection — the one bundled with the web client). */
  icon: string
  href: string
  status: ChamberStatus
  /** One-line positioning used in chamber-page metadata + nav strip. */
  tagline: string
}

// We use the ``solar:*`` Iconify collection rather than ``lucide:*``
// here because ``@iconify-json/solar`` is the only icon JSON bundled
// with the web client. Lucide icons would need a runtime fetch from
// api.iconify.design, which our production CSP's ``connect-src``
// doesn't allow — so they render as empty spans in the pill strip.
export const CHAMBERS: readonly Chamber[] = [
  {
    id: 'secret',
    label: 'Secret',
    icon: 'solar:lock-linear',
    href: '/secret',
    status: 'live',
    tagline: 'Share a one-time secret that self-destructs on open.',
  },
]
