'use client'

import createGlobe, { type Arc, type Marker } from 'cobe'
import { useEffect, useRef } from 'react'

// COBE-powered globe for the landing — same library Linear, Vercel,
// Cal.com use for their hero globes. ~5 KB, zero deps, WebGL.
//
// Visual story: every dot is a Rapidly user's browser; every arc is
// a file moving directly between two of them. No central server in
// any of those lines — that's the brand promise rendered.
//
// Implementation:
// - The globe runs on a single canvas; a ref-based render loop
//   updates ``phi`` for slow rotation.
// - Drag-to-rotate is wired via pointer events that adjust ``phi``
//   directly.
// - Markers are static dots at world cities (rough lat/lng).
// - Arcs cycle through a list of (from, to) pairs to simulate live
//   peer-to-peer transfers happening worldwide.
// - prefers-reduced-motion stops both the rotation and the arc
//   cycling so users who opted out get a still globe.
// - Light + dark mode swap the colour palette via the
//   ``isDark`` prop (caller passes the resolved theme).

interface City {
  name: string
  lat: number
  lng: number
}

const CITIES: City[] = [
  { name: 'New York', lat: 40.71, lng: -74.0 },
  { name: 'San Francisco', lat: 37.77, lng: -122.42 },
  { name: 'London', lat: 51.5, lng: -0.13 },
  { name: 'Berlin', lat: 52.52, lng: 13.4 },
  { name: 'Tokyo', lat: 35.68, lng: 139.69 },
  { name: 'Sydney', lat: -33.87, lng: 151.21 },
  { name: 'São Paulo', lat: -23.55, lng: -46.63 },
  { name: 'Mumbai', lat: 19.07, lng: 72.88 },
  { name: 'Singapore', lat: 1.35, lng: 103.82 },
  { name: 'Cape Town', lat: -33.92, lng: 18.42 },
  { name: 'Toronto', lat: 43.65, lng: -79.38 },
  { name: 'Paris', lat: 48.85, lng: 2.35 },
]

// Simulated active transfer pairs — cycle through these to look
// ""live"". With ~12 pairs and 4-second cycles, the globe feels
// constantly active without ever repeating in a way that's
// obviously a loop.
const TRANSFER_PAIRS: ReadonlyArray<readonly [number, number]> = [
  [0, 4], // NY → Tokyo
  [1, 2], // SF → London
  [3, 7], // Berlin → Mumbai
  [5, 8], // Sydney → Singapore
  [6, 11], // São Paulo → Paris
  [9, 0], // Cape Town → NY
  [10, 3], // Toronto → Berlin
  [4, 5], // Tokyo → Sydney
  [2, 8], // London → Singapore
  [11, 7], // Paris → Mumbai
  [1, 4], // SF → Tokyo
  [0, 5], // NY → Sydney
]

interface RapidlyGlobeProps {
  isDark?: boolean
  size?: number
}

export function RapidlyGlobe({
  isDark = false,
  size = 600,
}: RapidlyGlobeProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const phiRef = useRef(0)
  const pointerInteractingRef = useRef<number | null>(null)
  const pointerInteractionMovementRef = useRef(0)

  useEffect(() => {
    if (!canvasRef.current) return

    const reduceMotion = window.matchMedia(
      '(prefers-reduced-motion: reduce)',
    ).matches

    const markers: Marker[] = CITIES.map((c) => ({
      location: [c.lat, c.lng],
      size: 0.04,
    }))

    // Initial arcs — cycled below via setInterval.
    const buildArcs = (offset: number): Arc[] =>
      TRANSFER_PAIRS.slice(offset, offset + 4).map(([fromIdx, toIdx]) => ({
        from: [CITIES[fromIdx].lat, CITIES[fromIdx].lng],
        to: [CITIES[toIdx].lat, CITIES[toIdx].lng],
      }))

    let arcOffset = 0
    let arcs = buildArcs(arcOffset)

    const globe = createGlobe(canvasRef.current, {
      devicePixelRatio: 2,
      width: size * 2,
      height: size * 2,
      phi: 0,
      theta: 0.3,
      dark: isDark ? 1 : 0,
      diffuse: 1.2,
      mapSamples: 16000,
      mapBrightness: isDark ? 4 : 1.2,
      // Warm cream theme — pulled from the existing ``--beige-*``
      // palette so the globe sits naturally on the page background.
      baseColor: isDark ? [0.3, 0.3, 0.3] : [0.95, 0.92, 0.88],
      markerColor: isDark ? [0.95, 0.6, 0.2] : [0.85, 0.45, 0.1], // amber
      glowColor: isDark ? [0.3, 0.25, 0.2] : [0.95, 0.92, 0.88],
      arcColor: isDark ? [0.4, 0.85, 0.6] : [0.2, 0.7, 0.5], // emerald
      arcWidth: 1.5,
      arcHeight: 0.5,
      markers,
      arcs,
    })

    // Drive rotation via requestAnimationFrame — cobe v2 doesn't
    // ship an onRender hook so we call ``update`` ourselves at 60 fps.
    let rafId = 0
    const tick = () => {
      if (!pointerInteractingRef.current && !reduceMotion) {
        phiRef.current += 0.003
      }
      globe.update({
        phi: phiRef.current + pointerInteractionMovementRef.current,
      })
      rafId = requestAnimationFrame(tick)
    }
    rafId = requestAnimationFrame(tick)

    // Cycle arcs to simulate live activity. Skipped on reduce-motion.
    const arcInterval = reduceMotion
      ? null
      : setInterval(() => {
          arcOffset = (arcOffset + 1) % TRANSFER_PAIRS.length
          arcs = buildArcs(arcOffset)
          globe.update({ arcs })
        }, 2500)

    // Fade-in once the globe has had a frame or two to render —
    // avoids a flash of the canvas at zero opacity / before WebGL
    // has uploaded textures.
    setTimeout(() => {
      if (canvasRef.current) canvasRef.current.style.opacity = '1'
    }, 100)

    return () => {
      if (arcInterval !== null) clearInterval(arcInterval)
      cancelAnimationFrame(rafId)
      globe.destroy()
    }
  }, [isDark, size])

  return (
    <div
      className="relative mx-auto"
      style={{ width: size, height: size, maxWidth: '100%' }}
    >
      <canvas
        ref={canvasRef}
        className="cursor-grab transition-opacity duration-700 active:cursor-grabbing"
        style={{
          width: '100%',
          height: '100%',
          contain: 'layout paint size',
          opacity: 0,
        }}
        onPointerDown={(e) => {
          pointerInteractingRef.current = e.clientX
          ;(e.currentTarget as HTMLCanvasElement).style.cursor = 'grabbing'
        }}
        onPointerUp={() => {
          pointerInteractingRef.current = null
        }}
        onPointerOut={() => {
          pointerInteractingRef.current = null
        }}
        onMouseMove={(e) => {
          if (pointerInteractingRef.current !== null) {
            const delta = e.clientX - pointerInteractingRef.current
            pointerInteractionMovementRef.current = delta / 200
            phiRef.current = phiRef.current + 0
          }
        }}
        onTouchMove={(e) => {
          if (pointerInteractingRef.current !== null && e.touches[0]) {
            const delta = e.touches[0].clientX - pointerInteractingRef.current
            pointerInteractionMovementRef.current = delta / 100
          }
        }}
      />
    </div>
  )
}
