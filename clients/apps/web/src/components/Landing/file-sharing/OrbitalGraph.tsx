'use client'

// Animated orbital network graph for the hero — visual metaphor for
// peer-to-peer sharing: a central ""file"" node, satellites orbiting
// at three radii, lines connecting center to each. Pure SVG + CSS
// keyframes (no canvas, no JS animation loop) so it costs nothing on
// idle and renders identically across browsers.
//
// Adapted from the visual language Graphify uses on its landing —
// same structural idea, mapped to Rapidly's positioning (file at the
// centre, recipients orbiting, encrypted P2P channels as the lines).

interface Satellite {
  /** Angle in degrees on the ring (0 = right, 90 = bottom). */
  angle: number
  /** Visual size of the dot. */
  size: number
}

const RING_INNER: Satellite[] = [
  { angle: 0, size: 5 },
  { angle: 90, size: 6 },
  { angle: 180, size: 4 },
  { angle: 270, size: 5 },
]

const RING_MIDDLE: Satellite[] = [
  { angle: 30, size: 6 },
  { angle: 100, size: 5 },
  { angle: 165, size: 7 },
  { angle: 220, size: 4 },
  { angle: 290, size: 6 },
]

const RING_OUTER: Satellite[] = [
  { angle: 15, size: 4 },
  { angle: 70, size: 5 },
  { angle: 135, size: 4 },
  { angle: 195, size: 6 },
  { angle: 255, size: 4 },
  { angle: 320, size: 5 },
]

const RADII = { inner: 70, middle: 120, outer: 170 }

// Satellite x/y for a ring of given radius given angle in degrees.
function pos(radius: number, angleDeg: number): { x: number; y: number } {
  const r = (angleDeg * Math.PI) / 180
  return {
    x: 200 + radius * Math.cos(r),
    y: 200 + radius * Math.sin(r),
  }
}

export function OrbitalGraph() {
  return (
    <div className="relative aspect-square w-full max-w-md">
      <svg
        viewBox="0 0 400 400"
        className="h-full w-full"
        aria-hidden
        role="presentation"
      >
        <defs>
          {/* Soft glow for nodes — sized so it's visible without
              washing out on light backgrounds. */}
          <filter
            id="orbital-glow"
            x="-50%"
            y="-50%"
            width="200%"
            height="200%"
          >
            <feGaussianBlur stdDeviation="3" result="blur" />
            <feMerge>
              <feMergeNode in="blur" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
          <filter
            id="orbital-glow-strong"
            x="-50%"
            y="-50%"
            width="200%"
            height="200%"
          >
            <feGaussianBlur stdDeviation="6" result="blur" />
            <feMerge>
              <feMergeNode in="blur" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
        </defs>

        {/* Connecting lines — drawn first so they sit behind nodes.
            Light mode: subtle slate; dark mode: subtle emerald. */}
        <g className="orbital-lines">
          {[...RING_INNER, ...RING_MIDDLE, ...RING_OUTER].map((sat, i) => {
            const radius =
              i < RING_INNER.length
                ? RADII.inner
                : i < RING_INNER.length + RING_MIDDLE.length
                  ? RADII.middle
                  : RADII.outer
            const { x, y } = pos(radius, sat.angle)
            return (
              <line
                key={`line-${i}`}
                x1={200}
                y1={200}
                x2={x}
                y2={y}
                strokeWidth={0.8}
              />
            )
          })}
        </g>

        {/* Three orbital rings — each rotates at a different speed.
            Inner ring rotates clockwise; middle counter-clockwise;
            outer clockwise. Different speeds give the organic-drift
            feel rather than ""everything spinning together"". */}
        <g className="orbital-ring orbital-ring--inner">
          {RING_INNER.map((sat, i) => {
            const { x, y } = pos(RADII.inner, sat.angle)
            return (
              <circle
                key={`inner-${i}`}
                cx={x}
                cy={y}
                r={sat.size}
                className="orbital-satellite"
                filter="url(#orbital-glow)"
              />
            )
          })}
        </g>

        <g className="orbital-ring orbital-ring--middle">
          {RING_MIDDLE.map((sat, i) => {
            const { x, y } = pos(RADII.middle, sat.angle)
            return (
              <circle
                key={`middle-${i}`}
                cx={x}
                cy={y}
                r={sat.size}
                className="orbital-satellite"
                filter="url(#orbital-glow)"
              />
            )
          })}
        </g>

        <g className="orbital-ring orbital-ring--outer">
          {RING_OUTER.map((sat, i) => {
            const { x, y } = pos(RADII.outer, sat.angle)
            return (
              <circle
                key={`outer-${i}`}
                cx={x}
                cy={y}
                r={sat.size}
                className="orbital-satellite"
                filter="url(#orbital-glow)"
              />
            )
          })}
        </g>

        {/* Centre ""file"" node — pulses gently. Warm amber against
            the cool emerald satellites, same colour pairing as
            Graphify (orange center / green satellites). */}
        <circle
          cx={200}
          cy={200}
          r={14}
          className="orbital-center"
          filter="url(#orbital-glow-strong)"
        />
      </svg>
    </div>
  )
}
