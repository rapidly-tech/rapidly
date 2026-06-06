'use client'

import { motion } from 'framer-motion'
import Link from 'next/link'

import { CHAMBERS } from '@/components/Chamber/chambers'

/**
 * Horizontal badge strip linking to the other chambers. Icons are
 * inlined from the Solar collection rather than fetched through
 * ``@iconify/react`` at runtime — the async CDN fetch was flaky in
 * production and several pills were rendering with an empty icon
 * slot. 24×24 SVGs from ``@iconify-json/solar`` pasted in verbatim so
 * the whole pill renders on first paint, no network round-trip.
 *
 * Pass ``currentId`` on chamber pages so we omit the chamber the
 * visitor is already on. Pass ``excludeIds`` to drop additional
 * chambers — e.g. the file-sharing landing (still served from
 * ``/`` until the engineering-suite landing replaces it) hides
 * Secret because the card already surfaces a secret entry point via
 * the "or type a secret..." button.
 */

const SVGS: Record<string, React.ReactNode> = {
  secret: (
    <g fill="none" stroke="currentColor" strokeWidth="1.5">
      <path d="M2 16c0-2.828 0-4.243.879-5.121C3.757 10 5.172 10 8 10h8c2.828 0 4.243 0 5.121.879C22 11.757 22 13.172 22 16s0 4.243-.879 5.121C20.243 22 18.828 22 16 22H8c-2.828 0-4.243 0-5.121-.879C2 20.243 2 18.828 2 16Z" />
      <path strokeLinecap="round" d="M6 10V8a6 6 0 1 1 12 0v2" />
    </g>
  ),
  collab: (
    <g fill="none" stroke="currentColor" strokeWidth="1.5">
      <circle cx="9" cy="6" r="4" />
      <path strokeLinecap="round" d="M15 9a3 3 0 1 0 0-6" />
      <ellipse cx="9" cy="17" rx="7" ry="4" />
      <path
        strokeLinecap="round"
        d="M18 14c1.754.385 3 1.359 3 2.5c0 1.03-1.014 1.923-2.5 2.37"
      />
    </g>
  ),
}

interface ChamberStripProps {
  currentId?: string
  excludeIds?: readonly string[]
}

export function ChamberStrip({ currentId, excludeIds }: ChamberStripProps) {
  // ``currentId`` used to default to ``'files'`` because the strip was
  // always rendered from the file-sharing landing. The Files chamber no
  // longer exists in the CHAMBERS registry (see chambers.ts header for
  // the engineering-suite framing decision), so the default is now no
  // exclusion — callers that render on a specific chamber page still
  // pass ``currentId={...}`` explicitly via ChamberPageShell.
  const hidden = new Set<string>([
    ...(currentId ? [currentId] : []),
    ...(excludeIds ?? []),
  ])
  const others = CHAMBERS.filter((c) => !hidden.has(c.id))

  return (
    <nav
      aria-label="Explore other chambers"
      className="animate-fade-in-up relative z-10 mx-auto grid grid-cols-2 gap-3 pt-4 pb-4 delay-100 md:flex md:flex-wrap md:items-center md:justify-center"
    >
      {others.map((chamber) => (
        <Link
          key={chamber.id}
          href={chamber.href}
          aria-label={`${chamber.label} — ${chamber.tagline}`}
          className="rounded-full focus-visible:ring-2 focus-visible:ring-slate-400 focus-visible:outline-none"
        >
          <motion.div
            className="glass-subtle flex items-center justify-center gap-x-2 rounded-full px-4 py-2"
            whileHover={{ scale: 1.06, y: -2 }}
            transition={{ type: 'spring', stiffness: 400, damping: 17 }}
          >
            <svg
              viewBox="0 0 24 24"
              className="h-3.5 w-3.5 text-slate-500 dark:text-slate-400"
              aria-hidden
            >
              {SVGS[chamber.id]}
            </svg>
            <span className="rp-text-secondary text-xs font-medium">
              {chamber.label}
            </span>
          </motion.div>
        </Link>
      ))}
    </nav>
  )
}
