'use client'

/**
 * Revolver — 6-chamber radial landing.
 *
 * Six chambers laid out on a hexagonal ring around a central "Rapidly"
 * mark. Each chamber is a clickable card (link or disabled button based
 * on its ``status``). Geometry is pure CSS transforms so the layout is
 * resolution-independent and does not rely on absolute pixel math.
 *
 * Behind the cards sits a low-opacity ``RadialRings`` backdrop whose
 * six inner wedges align 1:1 with the chamber cards, plus an outer
 * ring of sub-feature segments so the visualisation reads as a
 * product map rather than a generic radial chart.
 */

import { Icon } from '@iconify/react'
import Link from 'next/link'

import type { RingNode } from '@/utils/visualisation/radial-rings'
import { CHAMBERS, type Chamber } from './chambers'
import { RadialRings } from './RadialRings'

/** Radius of the chamber ring, expressed in rem so it scales with root font size. */
const RING_RADIUS_REM = 13

/** Decorative backdrop tree. Inner ring = six chambers (equal-
 *  weighted so each spans 60°). Outer ring = a few sub-features per
 *  chamber, lightly tinted in the chamber's accent so the wedges read
 *  as related-but-quieter. */
const BACKDROP_RINGS: RingNode = {
  id: 'rapidly',
  color: 'rgba(148, 163, 184, 0.04)',
  children: [
    {
      id: 'files',
      color: 'rgba(165, 216, 255, 0.18)',
      children: [
        { id: 'files-p2p', value: 1, color: 'rgba(165, 216, 255, 0.30)' },
        { id: 'files-e2ee', value: 1, color: 'rgba(165, 216, 255, 0.20)' },
        { id: 'files-link', value: 1, color: 'rgba(165, 216, 255, 0.12)' },
      ],
    },
    {
      id: 'secret',
      color: 'rgba(224, 169, 240, 0.18)',
      children: [
        { id: 'secret-vault', value: 1, color: 'rgba(224, 169, 240, 0.28)' },
        { id: 'secret-burn', value: 1, color: 'rgba(224, 169, 240, 0.16)' },
      ],
    },
    {
      id: 'screen',
      color: 'rgba(178, 242, 187, 0.18)',
      children: [
        { id: 'screen-share', value: 1, color: 'rgba(178, 242, 187, 0.28)' },
        { id: 'screen-record', value: 1, color: 'rgba(178, 242, 187, 0.18)' },
        { id: 'screen-cast', value: 1, color: 'rgba(178, 242, 187, 0.12)' },
      ],
    },
    {
      id: 'watch',
      color: 'rgba(255, 217, 168, 0.18)',
      children: [
        { id: 'watch-sync', value: 1, color: 'rgba(255, 217, 168, 0.28)' },
        { id: 'watch-rooms', value: 1, color: 'rgba(255, 217, 168, 0.16)' },
      ],
    },
    {
      id: 'call',
      color: 'rgba(255, 236, 153, 0.18)',
      children: [
        { id: 'call-voice', value: 1, color: 'rgba(255, 236, 153, 0.28)' },
        { id: 'call-video', value: 1, color: 'rgba(255, 236, 153, 0.18)' },
        { id: 'call-mesh', value: 1, color: 'rgba(255, 236, 153, 0.12)' },
      ],
    },
    {
      id: 'collab',
      color: 'rgba(252, 194, 215, 0.18)',
      children: [
        { id: 'collab-docs', value: 1, color: 'rgba(252, 194, 215, 0.28)' },
        { id: 'collab-board', value: 1, color: 'rgba(252, 194, 215, 0.16)' },
      ],
    },
  ],
}

interface RevolverProps {
  /** Optional override for the centre logo/mark. Defaults to the word mark. */
  centre?: React.ReactNode
}

export function Revolver({ centre }: RevolverProps) {
  return (
    <div className="relative mx-auto flex aspect-square w-full max-w-3xl items-center justify-center">
      {/* Decorative ring backdrop — sits behind the chamber cards.
          Rotated -30° so each 60° wedge centres under its matching
          card (the cards start at angle -90 i.e. 12 o'clock, while
          the ring's first wedge starts at 0° i.e. the right edge of
          12 o'clock and sweeps clockwise). */}
      <div
        aria-hidden
        className="pointer-events-none absolute inset-8 z-0 text-slate-400/40 dark:text-slate-500/30"
        style={{ transform: 'rotate(-30deg)' }}
      >
        <RadialRings
          data={BACKDROP_RINGS}
          radius={433}
          centerRadius={0.32}
          radiusScaleExponent={0.6}
          excludeRoot
          strokeColor="currentColor"
          strokeWidth={0.5}
          className="h-full w-full"
        />
      </div>
      {CHAMBERS.map((chamber, index) => (
        <ChamberCard
          key={chamber.id}
          chamber={chamber}
          angleDeg={index * 60 - 90}
        />
      ))}
      <div className="relative z-10 flex size-32 items-center justify-center rounded-full bg-gradient-to-br from-emerald-500 to-emerald-700 text-white shadow-xl shadow-emerald-600/30">
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
    <div className="absolute z-10" style={style}>
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
