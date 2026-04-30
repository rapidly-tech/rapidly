'use client'

import { CHAMBERS } from '@/components/Revolver/chambers'
import { Icon } from '@iconify/react'
import Link from 'next/link'

// Dome / arc section — adapted from the ""Powerful Integrations,
// Effortless Setup"" pattern (Lenora, Grovia and many other modern
// templates use this). Six chambers = our parallel to the brand
// integrations those templates show. Each chamber gets a floating
// rounded-square card sitting on a soft pale-gradient semi-circle.
//
// Layout: an SVG arc draws the curve; cards are absolute-positioned
// along it via trig (angle → x/y). Hidden on mobile because the
// dome footprint needs horizontal room — small screens fall back to
// the original ``ChamberStrip`` pill list.

// Small per-chamber accent for the icon — keeps each card visually
// distinct without saturating any of them.
const CHAMBER_TINT: Record<string, string> = {
  files: 'text-orange-500',
  secret: 'text-emerald-500',
  screen: 'text-sky-500',
  watch: 'text-amber-500',
  call: 'text-rose-500',
  collab: 'text-violet-500',
}

// Position the six cards along a half-circle. ``arcPositions`` are
// in (x, y) percentages relative to the dome container (0,0 = top-
// left, 100,100 = bottom-right). Centre card highest, edges lower —
// matches the Lenora reference where logos sit higher in the middle.
const ARC_POSITIONS = [
  { x: 8, y: 62 }, // far-left
  { x: 22, y: 28 }, // mid-left, high
  { x: 40, y: 8 }, // centre-left, highest
  { x: 60, y: 8 }, // centre-right, highest
  { x: 78, y: 28 }, // mid-right, high
  { x: 92, y: 62 }, // far-right
]

// Renders the dome arc + chamber cards as a self-contained block.
// Title / pill label live in the parent so the dome can sit
// around the dropzone without competing copy stacked on top.
export function ChambersDome() {
  return (
    <div className="relative w-full">
      {/* Dome with floating chamber cards. The arc itself is an SVG
          path (semi-ellipse) filled with a soft pale gradient; cards
          sit on top via absolute positioning. */}
      <div className="relative mx-auto hidden aspect-[16/7] w-full max-w-4xl md:block">
        {/* Pale gradient dome shape */}
        <svg
          viewBox="0 0 100 44"
          className="absolute inset-0 h-full w-full"
          aria-hidden
          preserveAspectRatio="none"
        >
          <defs>
            <linearGradient id="dome-grad" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="rgba(180, 200, 230, 0.0)" />
              <stop offset="50%" stopColor="rgba(200, 215, 235, 0.45)" />
              <stop offset="100%" stopColor="rgba(220, 230, 245, 0.25)" />
            </linearGradient>
            <linearGradient id="dome-grad-dark" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="rgba(40, 55, 80, 0)" />
              <stop offset="50%" stopColor="rgba(60, 75, 100, 0.45)" />
              <stop offset="100%" stopColor="rgba(40, 55, 80, 0.25)" />
            </linearGradient>
          </defs>
          {/* Half-ellipse: M start, A rx ry rot 0 0 to-x to-y, Z */}
          <path
            d="M 5 44 A 50 44 0 0 1 95 44 Z"
            className="fill-[url(#dome-grad)] dark:fill-[url(#dome-grad-dark)]"
          />
        </svg>

        {/* Floating chamber cards */}
        {CHAMBERS.slice(0, 6).map((chamber, i) => {
          const pos = ARC_POSITIONS[i]
          const tint = CHAMBER_TINT[chamber.id] ?? 'text-slate-500'
          // Subtle alternating rotation for the casually-placed feel
          // matching Lenora's reference.
          const rotate = i % 2 === 0 ? -6 : 6
          return (
            <Link
              key={chamber.id}
              href={chamber.href}
              aria-label={`${chamber.label} — ${chamber.tagline}`}
              className="group absolute focus-visible:ring-2 focus-visible:ring-slate-400 focus-visible:outline-none"
              style={{
                left: `${pos.x}%`,
                top: `${pos.y}%`,
                transform: `translate(-50%, -50%) rotate(${rotate}deg)`,
              }}
            >
              <div
                className={`flex h-16 w-16 items-center justify-center rounded-2xl border border-(--beige-border)/60 bg-white shadow-[0_8px_24px_rgba(120,100,80,0.10)] transition-transform duration-300 group-hover:scale-110 group-hover:shadow-[0_12px_32px_rgba(120,100,80,0.16)] dark:border-white/10 dark:bg-white/8 dark:backdrop-blur-xl ${tint}`}
              >
                <Icon icon={chamber.icon} className="h-7 w-7" aria-hidden />
              </div>
              <span className="rp-text-secondary mt-2 block text-center text-xs font-medium">
                {chamber.label}
              </span>
            </Link>
          )
        })}
      </div>

      {/* Mobile fallback — stacked grid since the arc doesn't have
          horizontal room on a phone. */}
      <div className="grid grid-cols-3 gap-4 md:hidden">
        {CHAMBERS.slice(0, 6).map((chamber) => {
          const tint = CHAMBER_TINT[chamber.id] ?? 'text-slate-500'
          return (
            <Link
              key={chamber.id}
              href={chamber.href}
              aria-label={`${chamber.label} — ${chamber.tagline}`}
              className="flex flex-col items-center gap-2 focus-visible:outline-none"
            >
              <div
                className={`flex h-14 w-14 items-center justify-center rounded-2xl border border-(--beige-border)/60 bg-white shadow-[0_4px_12px_rgba(120,100,80,0.08)] dark:border-white/10 dark:bg-white/8 dark:backdrop-blur-xl ${tint}`}
              >
                <Icon icon={chamber.icon} className="h-6 w-6" aria-hidden />
              </div>
              <span className="rp-text-secondary text-xs font-medium">
                {chamber.label}
              </span>
            </Link>
          )
        })}
      </div>
    </div>
  )
}
