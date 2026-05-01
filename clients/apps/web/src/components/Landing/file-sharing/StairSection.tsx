'use client'

import { useTheme } from 'next-themes'
import dynamic from 'next/dynamic'
import { useEffect, useState } from 'react'

// Lazy-load the stair — R3F + three is ~180 KB; deferring keeps
// the initial paint (hero + dropzone) fast.
const RapidlyStair = dynamic(
  () => import('./RapidlyStair').then((m) => ({ default: m.RapidlyStair })),
  { ssr: false },
)

// Section that hosts Paul Henschel's raycast cycling stair
// adapted for Rapidly. The header always renders server-side; only
// the WebGL canvas waits for client mount + theme resolution so
// the user sees the section instantly even if R3F is in flight.
export function StairSection() {
  const { resolvedTheme } = useTheme()
  const [mounted, setMounted] = useState(false)

  useEffect(() => setMounted(true), [])

  const isDark = resolvedTheme === 'dark'

  return (
    <section
      aria-label="Layered, private, peer-to-peer"
      className="relative z-10 mx-auto w-full max-w-6xl px-4 py-20 md:py-28"
    >
      <div className="mb-8 text-center md:mb-12">
        <h2 className="rp-text-primary text-3xl font-semibold tracking-tight md:text-4xl">
          Layered. Private. Yours.
        </h2>
        <p className="rp-text-secondary mx-auto mt-3 max-w-xl text-sm md:text-base">
          Every share is encrypted in the browser, streamed peer-to-peer, and
          gone when you say so.
        </p>
      </div>

      <div
        className="relative w-full overflow-hidden rounded-3xl"
        style={{ height: 600 }}
      >
        {mounted && <RapidlyStair isDark={isDark} />}
      </div>
    </section>
  )
}
