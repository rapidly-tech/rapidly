'use client'

import { useTheme } from 'next-themes'
import dynamic from 'next/dynamic'
import { useEffect, useState } from 'react'

// Lazy-load the globe — cobe is small but it pulls in WebGL on
// first paint, so deferring until after the hero is interactive
// keeps initial-load fast.
const RapidlyGlobe = dynamic(
  () => import('./RapidlyGlobe').then((m) => ({ default: m.RapidlyGlobe })),
  { ssr: false },
)

// Hero-adjacent section — globe + caption that describes the brand
// promise. Pattern lifted from Linear / Vercel / Cal.com landings:
// big visual centerpiece with a tight one-liner above and a
// reinforcement line below.
export function GlobeSection() {
  const { resolvedTheme } = useTheme()
  const [mounted, setMounted] = useState(false)

  // ``next-themes`` returns ``undefined`` until the client has
  // hydrated. Wait for mount so the globe initialises with the
  // correct dark/light palette instead of flashing wrong-mode.
  useEffect(() => setMounted(true), [])

  if (!mounted) return null

  const isDark = resolvedTheme === 'dark'

  return (
    <section
      aria-label="Rapidly works peer-to-peer worldwide"
      className="relative z-10 mx-auto w-full max-w-5xl px-4 py-20 md:py-28"
    >
      <div className="mb-8 text-center md:mb-12">
        <h2 className="rp-text-primary text-3xl font-semibold tracking-tight md:text-4xl">
          Peer-to-peer, everywhere.
        </h2>
        <p className="rp-text-secondary mx-auto mt-3 max-w-xl text-sm md:text-base">
          Every dot is a browser. Every arc is a file moving directly between
          two of them. Our server isn&apos;t in any of those lines.
        </p>
      </div>

      <div className="relative flex items-center justify-center">
        <RapidlyGlobe isDark={isDark} size={600} />
      </div>
    </section>
  )
}
