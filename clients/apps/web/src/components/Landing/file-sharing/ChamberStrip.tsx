'use client'

import { Icon } from '@iconify/react'
import { motion } from 'framer-motion'
import Link from 'next/link'

import { CHAMBERS } from '@/components/Revolver/chambers'

/**
 * Horizontal pill strip advertising the other chambers. Matches the
 * trust-badge visual language (glass-subtle + rounded-full) so it reads
 * as part of the hero, not bolted on. Pass ``currentId`` on chamber
 * pages so we omit the chamber the visitor is already on.
 */
export function ChamberStrip({ currentId = 'files' }: { currentId?: string }) {
  const others = CHAMBERS.filter((c) => c.id !== currentId)

  return (
    <motion.nav
      aria-label="Explore other chambers"
      className="relative z-10 mx-auto flex flex-wrap items-center justify-center gap-2 py-4"
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0, transition: { duration: 0.3, delay: 0.15 } }}
    >
      {others.map((chamber) => (
        <motion.div
          key={chamber.id}
          whileHover={{ scale: 1.06, y: -2 }}
          transition={{ type: 'spring', stiffness: 400, damping: 17 }}
        >
          <Link
            href={chamber.href}
            aria-label={`${chamber.label} — ${chamber.tagline}`}
            className="glass-subtle rp-text-secondary hover:rp-text-primary flex items-center gap-x-2 rounded-full px-4 py-2 text-xs font-medium transition-colors"
          >
            <Icon
              icon={chamber.icon}
              className="h-3.5 w-3.5 text-slate-500 dark:text-slate-400"
              aria-hidden
            />
            <span>{chamber.label}</span>
          </Link>
        </motion.div>
      ))}
    </motion.nav>
  )
}
