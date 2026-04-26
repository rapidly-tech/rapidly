'use client'

/**
 * Revolver — 6-chamber radial landing.
 *
 * Six chambers laid out on a hexagonal ring around a central "Rapidly"
 * mark. Each chamber is a clickable card (link or disabled button based
 * on its ``status``). Geometry is pure CSS transforms so the layout is
 * resolution-independent and does not rely on absolute pixel math.
 */

import { Icon } from '@iconify/react'
import Link from 'next/link'

import { CHAMBERS, type Chamber } from './chambers'

/** Radius of the chamber ring, expressed in rem so it scales with root font size. */
const RING_RADIUS_REM = 13

interface RevolverProps {
  /** Optional override for the centre logo/mark. Defaults to the word mark. */
  centre?: React.ReactNode
}

export function Revolver({ centre }: RevolverProps) {
  return (
    <div className="relative mx-auto flex aspect-square w-full max-w-3xl items-center justify-center">
      {CHAMBERS.map((chamber, index) => (
        <ChamberCard
          key={chamber.id}
          chamber={chamber}
          angleDeg={index * 60 - 90}
        />
      ))}
      <div className="relative flex size-32 items-center justify-center rounded-full bg-gradient-to-br from-emerald-500 to-emerald-700 text-white shadow-xl shadow-emerald-600/30">
        {centre ?? (
          <span className="text-lg font-semibold tracking-tight">Rapidly</span>
        )}
      </div>
    </div>
  )
}

interface ChamberCardProps {
  chamber: Chamber
  angleDeg: number
}

function ChamberCard({ chamber, angleDeg }: ChamberCardProps) {
  // Position on the ring. We compose transforms as: rotate around centre,
  // translate outward, rotate back so the card is upright. This avoids
  // sin/cos math in JS and stays readable.
  const style = {
    transform: `rotate(${angleDeg}deg) translate(${RING_RADIUS_REM}rem) rotate(${-angleDeg}deg)`,
  }

  const isLive = chamber.status === 'live'
  const body = (
    <div
      className={
        'flex size-32 flex-col items-center justify-center gap-1 rounded-2xl border bg-white/80 p-3 text-center shadow-md backdrop-blur transition-transform hover:scale-105 dark:bg-slate-900/70 ' +
        (isLive
          ? 'border-emerald-200 text-slate-900 dark:border-emerald-900 dark:text-white'
          : 'border-slate-200 text-slate-400 dark:border-slate-800 dark:text-slate-500')
      }
    >
      <Icon icon={chamber.icon} width={28} height={28} aria-hidden />
      <span className="text-sm font-medium">{chamber.label}</span>
      {!isLive && (
        <span className="rounded-full bg-amber-100 px-2 py-0.5 text-xs text-amber-700 dark:bg-amber-900/30 dark:text-amber-300">
          soon
        </span>
      )}
    </div>
  )

  return (
    <div className="absolute" style={style}>
      {isLive ? (
        <Link
          href={chamber.href}
          aria-label={`${chamber.label} — ${chamber.tagline}`}
          className="block rounded-2xl focus:ring-2 focus:ring-emerald-500 focus:ring-offset-2 focus:outline-none"
        >
          {body}
        </Link>
      ) : (
        <button
          type="button"
          disabled
          aria-label={`${chamber.label} — ${chamber.tagline} (coming soon)`}
          className="cursor-not-allowed rounded-2xl focus:ring-2 focus:ring-slate-400 focus:ring-offset-2 focus:outline-none"
        >
          {body}
        </button>
      )}
    </div>
  )
}
