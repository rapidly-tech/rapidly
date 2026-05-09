'use client'

/**
 * Standard layout for a chamber page (/secret, /screen, /watch, /call,
 * /collab). Renders the same hero treatment as the file-sharing landing
 * — big title + subtitle above, action area in the middle, chamber
 * strip below — so every chamber reads like part of the same product
 * instead of a standalone route with its own visual grammar.
 */

import { AnimatePresence, motion } from 'framer-motion'
import { ReactNode } from 'react'

import { ChamberStrip } from '@/components/Landing/file-sharing/ChamberStrip'

interface ChamberPageShellProps {
  title: string
  subtitle: string
  currentId: string
  children: ReactNode
}

export function ChamberPageShell({
  title,
  subtitle,
  currentId,
  children,
}: ChamberPageShellProps) {
  return (
    <div className="relative flex flex-1 flex-col items-center px-4 pt-4">
      <AnimatePresence mode="wait" initial={false}>
        <motion.div
          key={title}
          className="animate-fade-in-up relative z-10 mb-6 text-center"
          initial={{ opacity: 0, y: -8 }}
          animate={{ opacity: 1, y: 0, transition: { duration: 0.3 } }}
        >
          <h1 className="rp-text-primary text-3xl leading-tight! font-semibold tracking-tight md:text-5xl">
            {title}
          </h1>
          <p className="rp-text-secondary mt-4 text-base font-medium tracking-wide">
            {subtitle}
          </p>
        </motion.div>
      </AnimatePresence>

      {/* max-w-2xl matches FileSharingLandingPage's card column so every
          chamber reads the same as Send Secret does from the front page —
          tight, centred, not stretched to the page's full width. Chamber
          active states that legitimately need more room (e.g. Screen's
          video preview) still break out via their own max-width. */}
      <div className="relative mx-auto w-full max-w-2xl pb-6">{children}</div>

      <ChamberStrip currentId={currentId} />
    </div>
  )
}
