/**
 * Registry of the 6 chambers rendered by the Revolver landing.
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
  /** One-line positioning used in tooltips and the chamber card aria-label. */
  tagline: string
}

// We use the ``solar:*`` Iconify collection rather than ``lucide:*``
// here because ``@iconify-json/solar`` is the only icon JSON bundled
// with the web client. Lucide icons would need a runtime fetch from
// api.iconify.design, which our production CSP's ``connect-src``
// doesn't allow — so they render as empty spans in the pill strip.
export const CHAMBERS: readonly Chamber[] = [
  {
    id: 'files',
    label: 'Files',
    icon: 'solar:file-linear',
    // Public share flow at /files. NOT /dashboard — that's
    // auth-gated and bounces visitors to /login.
    href: '/files',
    status: 'live',
    tagline: 'End-to-end encrypted P2P file transfer.',
  },
  {
    id: 'secret',
    label: 'Secret',
    icon: 'solar:lock-linear',
    href: '/secret',
    status: 'live',
    tagline: 'Share a one-time secret that self-destructs on open.',
  },
  {
    id: 'screen',
    label: 'Screen',
    icon: 'solar:monitor-linear',
    href: '/screen',
    status: 'live',
    tagline: 'P2P screen share — no accounts, no servers relaying video.',
  },
  {
    id: 'watch',
    label: 'Watch',
    icon: 'solar:play-linear',
    href: '/watch',
    status: 'live',
    tagline: 'Watch together, perfectly synced.',
  },
  {
    id: 'call',
    label: 'Call',
    icon: 'solar:phone-linear',
    href: '/call',
    status: 'live',
    tagline: 'Encrypted voice + video for 1:1 and small groups.',
  },
  {
    id: 'collab',
    label: 'Collab',
    icon: 'solar:users-group-rounded-linear',
    href: '/collab',
    status: 'live',
    tagline: 'Realtime docs and whiteboards, locally-first.',
  },
]
