'use client'

import dynamic from 'next/dynamic'
import { useEffect, useState } from 'react'

// Lazy-load the stair — R3F + three is ~180 KB; deferring keeps
// the initial paint (hero + dropzone) fast.
const RapidlyStair = dynamic(
  () => import('./RapidlyStair').then((m) => ({ default: m.RapidlyStair })),
  { ssr: false },
)

// Section that hosts the frosted-glass stair scene. The header
// renders server-side; only the WebGL canvas waits for client mount
// so users see the section instantly.
export function StairSection() {
  const [mounted, setMounted] = useState(false)
  useEffect(() => setMounted(true), [])

  return (
    <section
      aria-label="Layered, private, peer-to-peer"
      // Full-bleed white-90 surface matches the demo's page wrapper
      // (``bg-white/90``). Breaks out of the page's cream theme so
      // the panels float against the same near-white background the
      // original demo uses, which is what keeps the shadows looking
      // subtle instead of dominant.
      className="relative z-10 w-full bg-white/90 py-20 md:py-28 dark:bg-white/5"
    >
      <div className="mx-auto max-w-6xl px-4">
        <div className="mb-8 text-center md:mb-12">
          <h2 className="text-3xl font-semibold tracking-tight text-slate-900 md:text-4xl dark:text-slate-100">
            Layered. Private. Yours.
          </h2>
          <p className="mx-auto mt-3 max-w-xl text-sm text-slate-600 md:text-base dark:text-slate-400">
            Every share is encrypted in the browser, streamed peer-to-peer,
            and gone when you say so.
          </p>
        </div>

        <div className="relative w-full" style={{ height: 600 }}>
          {mounted && <RapidlyStair />}
        </div>
      </div>
    </section>
  )
}
