'use client'

import dynamic from 'next/dynamic'
import { useEffect, useState } from 'react'
import { ChamberStrip } from './ChamberStrip'

// Lazy-load the stair — R3F + three is ~180 KB; deferring keeps
// the initial paint fast.
const RapidlyStair = dynamic(
  () => import('./RapidlyStair').then((m) => ({ default: m.RapidlyStair })),
  { ssr: false },
)

// Detects whether WebGL is available so we can render a fallback
// (the chamber pill strip) on browsers / devices that can't draw
// the 3D canvas. Runs once on mount; the result is stable for the
// session.
function detectWebGL(): boolean {
  if (typeof window === 'undefined') return false
  try {
    const canvas = document.createElement('canvas')
    return !!(canvas.getContext('webgl2') || canvas.getContext('webgl'))
  } catch {
    return false
  }
}

// Hero visual — the spiral stair of chambers. WebGL-capable browsers
// get the 3D scene; everything else falls back to the chamber pill
// strip (so the page is still functional / discoverable without
// 3D). Component is the only thing rendered in the hero ""action""
// slot when in initial direct mode.
export function StairSection() {
  const [mounted, setMounted] = useState(false)
  const [webgl, setWebgl] = useState(true)

  useEffect(() => {
    setMounted(true)
    setWebgl(detectWebGL())
  }, [])

  if (mounted && !webgl) {
    return (
      <div className="flex flex-col items-center gap-6 py-8">
        <p className="rp-text-muted max-w-md text-center text-sm">
          Your browser doesn&apos;t support WebGL. Pick a chamber to get
          started.
        </p>
        <ChamberStrip />
      </div>
    )
  }

  return (
    <div className="relative w-full" style={{ height: 600 }}>
      {mounted && <RapidlyStair />}
    </div>
  )
}
