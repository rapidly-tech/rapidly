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
  /** Iconify icon name (e.g. ``lucide:file``). */
  icon: string
  href: string
  status: ChamberStatus
  /** One-line positioning used in tooltips and the chamber card aria-label. */
  tagline: string
}

export const CHAMBERS: readonly Chamber[] = [
  {
    id: 'files',
    label: 'Files',
    icon: 'lucide:file',
    href: '/dashboard',
    status: 'live',
    tagline: 'End-to-end encrypted P2P file transfer.',
  },
  {
    id: 'secret',
    label: 'Secret',
    icon: 'lucide:lock',
    href: '/secret',
    status: 'live',
    tagline: 'Share a one-time secret that self-destructs on open.',
  },
  {
    id: 'screen',
    label: 'Screen',
    icon: 'lucide:monitor',
    href: '/screen',
    status: 'live',
    tagline: 'P2P screen share — no accounts, no servers relaying video.',
  },
  {
    id: 'watch',
    label: 'Watch',
    icon: 'lucide:play',
    href: '/watch',
    status: 'live',
    tagline: 'Watch together, perfectly synced.',
  },
  {
    id: 'call',
    label: 'Call',
    icon: 'lucide:phone',
    href: '/call',
    status: 'live',
    tagline: 'Encrypted voice + video for 1:1 and small groups.',
  },
  {
    id: 'collab',
    label: 'Collab',
    icon: 'lucide:users',
    href: '/collab',
    status: 'soon',
    tagline: 'Realtime docs and whiteboards, locally-first.',
  },
]
