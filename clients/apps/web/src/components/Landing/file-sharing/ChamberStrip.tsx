'use client'

import { Icon } from '@iconify/react'
import { motion } from 'framer-motion'
import Link from 'next/link'

import { CHAMBERS } from '@/components/Revolver/chambers'

/**
 * Horizontal badge strip linking to the other chambers. Mirrors the
 * former trust-badge pattern exactly (``glass-subtle`` on a
 * ``motion.div`` wrapper, icon + label) and wraps each pill in a Next
 * ``<Link>`` so the chamber names are the navigation.
 *
 * Pass ``currentId`` on chamber pages so we omit the chamber the
 * visitor is already on (defaults to ``files`` for the landing).
 */
export function ChamberStrip({ currentId = 'files' }: { currentId?: string }) {
  const others = CHAMBERS.filter((c) => c.id !== currentId)

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
            <Icon
              icon={chamber.icon}
              className="h-3.5 w-3.5 text-slate-500 dark:text-slate-400"
              aria-hidden
            />
            <span className="rp-text-secondary text-xs font-medium">
              {chamber.label}
            </span>
          </motion.div>
        </Link>
      ))}
    </nav>
  )
}
