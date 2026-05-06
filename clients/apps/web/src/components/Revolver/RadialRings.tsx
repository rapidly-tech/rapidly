'use client'

/**
 * RadialRings — concentric annular ring segments rendered as SVG.
 *
 * Pure presentation. The layout / arc-path math lives in
 * ``utils/visualisation/radial-rings.ts``; this component just maps
 * arcs to ``<path>`` elements, manages hover state, and exposes an
 * optional click handler.
 *
 * The component renders into a square viewBox of ``2*radius x
 * 2*radius`` centred at the origin, so callers can size it via CSS
 * (``className`` / ``style``) without re-laying out the geometry.
 */

import { useMemo, useState } from 'react'

import {
  arcCentroid,
  arcPath,
  layoutRingTree,
  type RingArc,
  type RingNode,
} from '@/utils/visualisation/radial-rings'

interface Props {
  data: RingNode
  /** SVG world-space radius of the deepest ring. The component uses
   *  this to set the viewBox; CSS controls the rendered size. */
  radius?: number
  centerRadius?: number
  radiusScaleExponent?: number
  /** Show the node label in each arc when there's room. Defaults to
   *  ``false`` since the decorative use case in DropZone doesn't want
   *  text noise; data-driven callers flip it on. */
  showLabels?: boolean
  /** Optional click handler — receives the arc's id. */
  onArcClick?: (id: string) => void
  /** Class applied to the outer ``<svg>`` so callers can size /
   *  position via Tailwind without prop drilling. */
  className?: string
  /** Skip the root arc from the paint output. The root usually
   *  represents the universe and is redundant when the caller wants
   *  the chart to look like an open ring rather than a filled disc. */
  excludeRoot?: boolean
  /** Stroke colour applied to every arc. Defaults to the host's
   *  ``currentColor`` so callers control via Tailwind text colour. */
  strokeColor?: string
  /** Stroke width in SVG units. Default ``1``. */
  strokeWidth?: number
}

const DEFAULT_RADIUS = 100

export function RadialRings({
  data,
  radius = DEFAULT_RADIUS,
  centerRadius,
  radiusScaleExponent,
  showLabels = false,
  onArcClick,
  className,
  excludeRoot = false,
  strokeColor = 'currentColor',
  strokeWidth = 1,
}: Props) {
  const [hovered, setHovered] = useState<string | null>(null)

  const arcs = useMemo(
    () =>
      layoutRingTree(data, {
        radius,
        centerRadius,
        radiusScaleExponent,
      }),
    [data, radius, centerRadius, radiusScaleExponent],
  )

  const visibleArcs: RingArc[] = useMemo(
    () => (excludeRoot ? arcs.filter((a) => a.depth > 0) : arcs),
    [arcs, excludeRoot],
  )

  return (
    <svg
      viewBox={`${-radius} ${-radius} ${radius * 2} ${radius * 2}`}
      preserveAspectRatio="xMidYMid meet"
      className={className}
      role="img"
      aria-hidden="true"
    >
      {visibleArcs.map((arc) => {
        const path = arcPath(arc)
        const isHovered = hovered === arc.id
        return (
          <g key={arc.id}>
            <path
              d={path}
              fill={arc.color}
              fillOpacity={isHovered ? 1 : 0.85}
              stroke={strokeColor}
              strokeWidth={strokeWidth}
              style={{
                transition: 'fill-opacity 200ms ease',
                cursor: onArcClick ? 'pointer' : 'default',
              }}
              onMouseEnter={() => setHovered(arc.id)}
              onMouseLeave={() => setHovered((h) => (h === arc.id ? null : h))}
              onClick={onArcClick ? () => onArcClick(arc.id) : undefined}
            />
            {showLabels &&
            arc.endAngle - arc.startAngle > 0.15 &&
            arc.outerRadius - arc.innerRadius > 8 ? (
              <ArcLabel arc={arc} />
            ) : null}
          </g>
        )
      })}
    </svg>
  )
}

function ArcLabel({ arc }: { arc: RingArc }) {
  const c = arcCentroid(arc)
  return (
    <text
      x={c.x}
      y={c.y}
      textAnchor="middle"
      dominantBaseline="middle"
      fontSize={Math.min(12, (arc.outerRadius - arc.innerRadius) * 0.4)}
      fill="currentColor"
      pointerEvents="none"
      style={{ userSelect: 'none' }}
    >
      {arc.label}
    </text>
  )
}
