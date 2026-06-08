/**
 * Registry of the 2 public product chambers (Secret / Markup). Used by
 * the chamber-strip nav on the public landing and by per-chamber page
 * metadata.
 *
 * What's gone vs. the original six-chamber product:
 * - Files: file_sharing is kept in code as transport infrastructure
 *   (powers the markup chamber and /share/<slug> anonymous-receive),
 *   but no longer surfaced as a top-level chamber per the engineering-
 *   suite framing decision (RAPIDLY_ENGINEERING_SUITE_PLAN.md §2.6).
 * - Screen / Watch / Call: the media chambers are consumer-y, not
 *   engineering use cases. Removed entirely (M1.1 in M1_EXECUTION.md).
 *
 * What remains here is intentionally small — Secret as a no-account
 * one-time-message surface, Markup as the engineering-markup chamber
 * (renamed from Collab in M1.4; internal identifiers in
 * sharing/markup/ still use the historical ``collab`` prefix and the
 * Redis key namespace ``file-sharing:collab:*`` stays the same to
 * preserve in-flight session compatibility). Both stay because they
 * map cleanly to engineering workflows (a quick share with a
 * consultant; a live drawing markup session).
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
  {
    id: 'markup',
    label: 'Markup',
    icon: 'solar:users-group-rounded-linear',
    href: '/markup',
    status: 'live',
    tagline: 'Realtime engineering markup on PDFs, images, and models.',
  },
]
