'use client'

/**
 * RadialRings — concentric annular ring segments rendered as SVG.
 *
 * Pure presentation. Layout / arc-path math lives in
 * ``utils/visualisation/radial-rings.ts``; this component maps arcs
 * to ``<path>`` elements, manages hover, and exposes a click +
 * keyboard handler so the rings can be used as primary navigation
 * (six-chamber landing) and not just a decorative backdrop.
 *
 * Accessibility
 * -------------
 *   - Interactive arcs get ``role="button"``, ``tabIndex``,
 *     ``aria-label`` (via ``getAriaLabel``), and respond to Enter +
 *     Space. The component as a whole is ``aria-hidden`` only when
 *     no click handler is supplied (the decorative case).
 *
 * Hover tooltip
 * -------------
 *   When ``getTooltip`` returns a string for a hovered arc, the
 *   tooltip floats near the cursor in screen-pixel space (not the
 *   SVG world). Implemented as an HTML overlay so the text is
 *   crisp at every zoom level.
 */

import { useMemo, useRef, useState } from 'react'

import {
  arcCentroid,
  arcPath,
  layoutRingTree,
  type RingArc,
  type RingNode,
} from '@/utils/visualisation/radial-rings'

interface Props {
  data: RingNode
  /** SVG world-space radius of the deepest ring. Sets the viewBox;
   *  CSS controls the rendered size. */
  radius?: number
  centerRadius?: number
  radiusScaleExponent?: number
  /** Per-arc shown text. Falls back to the node's ``label``. Use
   *  this to suppress labels on outer-ring sub-features while
   *  keeping them on inner-ring chambers. */
  getLabel?: (arc: RingArc) => string | undefined
  /** Per-arc accessible name (read by screen readers when an arc
   *  is interactive). Falls back to the resolved label. */
  getAriaLabel?: (arc: RingArc) => string | undefined
  /** Per-arc tooltip body. Returning ``undefined`` hides the
   *  tooltip for that arc even when one is hovered. */
  getTooltip?: (arc: RingArc) => string | undefined
  /** Whether a given arc accepts clicks. Defaults to "all when
   *  ``onArcClick`` is set". Use this to make only inner-ring
   *  chambers clickable while outer-ring sub-features stay
   *  decorative. */
  isInteractive?: (arc: RingArc) => boolean
  /** Optional click handler. Use with ``isInteractive`` to scope
   *  which arcs respond. */
  onArcClick?: (id: string, arc: RingArc) => void
  className?: string
  /** Skip the root arc from the paint output. */
  excludeRoot?: boolean
  /** Stroke colour applied to every arc. Defaults to
   *  ``currentColor``. */
  strokeColor?: string
  strokeWidth?: number
  /** Bump label font size — useful when the rings are the primary
   *  nav and need to read at glance. */
  labelScale?: number
}

const DEFAULT_RADIUS = 100

export function RadialRings({
  data,
  radius = DEFAULT_RADIUS,
  centerRadius,
  radiusScaleExponent,
  getLabel,
  getAriaLabel,
  getTooltip,
  isInteractive,
  onArcClick,
  className,
  excludeRoot = false,
  strokeColor = 'currentColor',
  strokeWidth = 1,
  labelScale = 1,
}: Props) {
  const [hovered, setHovered] = useState<string | null>(null)
  const [tooltip, setTooltip] = useState<{
    x: number
    y: number
    text: string
  } | null>(null)
  const wrapperRef = useRef<HTMLDivElement | null>(null)

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

  const arcIsClickable = (arc: RingArc): boolean => {
    if (!onArcClick) return false
    return isInteractive ? isInteractive(arc) : true
  }

  const handlePointerMove = (
    arc: RingArc,
    e: React.PointerEvent<SVGElement>,
  ): void => {
    if (!getTooltip) return
    const text = getTooltip(arc)
    if (!text) {
      setTooltip(null)
      return
    }
    const wrapper = wrapperRef.current
    if (!wrapper) return
    const rect = wrapper.getBoundingClientRect()
    setTooltip({
      x: e.clientX - rect.left,
      y: e.clientY - rect.top,
      text,
    })
  }

  return (
    <div
      ref={wrapperRef}
      className={`relative ${className ?? ''}`}
      onMouseLeave={() => setTooltip(null)}
    >
      <svg
        viewBox={`${-radius} ${-radius} ${radius * 2} ${radius * 2}`}
        preserveAspectRatio="xMidYMid meet"
        className="block h-full w-full"
        role={onArcClick ? 'group' : 'img'}
        aria-hidden={onArcClick ? undefined : 'true'}
      >
        {visibleArcs.map((arc) => {
          const path = arcPath(arc)
          const isHovered = hovered === arc.id
          const clickable = arcIsClickable(arc)
          const label = getLabel ? getLabel(arc) : arc.label
          const aria = getAriaLabel ? (getAriaLabel(arc) ?? label) : label
          const showLabel =
            !!label &&
            arc.endAngle - arc.startAngle > 0.18 &&
            arc.outerRadius - arc.innerRadius > 10
          return (
            <g
              key={arc.id}
              role={clickable ? 'button' : undefined}
              tabIndex={clickable ? 0 : undefined}
              aria-label={clickable ? aria : undefined}
              onKeyDown={
                clickable
                  ? (e) => {
                      if (e.key === 'Enter' || e.key === ' ') {
                        e.preventDefault()
                        onArcClick?.(arc.id, arc)
                      }
                    }
                  : undefined
              }
              style={{ outline: 'none' }}
            >
              <path
                d={path}
                fill={arc.color}
                fillOpacity={isHovered ? 1 : 0.85}
                stroke={strokeColor}
                strokeWidth={strokeWidth}
                style={{
                  transition: 'fill-opacity 180ms ease',
                  cursor: clickable ? 'pointer' : 'default',
                }}
                onMouseEnter={() => setHovered(arc.id)}
                onMouseLeave={() =>
                  setHovered((h) => (h === arc.id ? null : h))
                }
                onPointerMove={(e) => handlePointerMove(arc, e)}
                onClick={
                  clickable ? () => onArcClick?.(arc.id, arc) : undefined
                }
              />
              {showLabel ? (
                <ArcLabel arc={arc} text={label!} scale={labelScale} />
              ) : null}
            </g>
          )
        })}
      </svg>
      {tooltip ? (
        <div
          role="tooltip"
          className="pointer-events-none absolute z-20 -translate-x-1/2 -translate-y-full rounded-md bg-slate-900/95 px-2 py-1 text-xs font-medium text-white shadow-lg dark:bg-slate-100/95 dark:text-slate-900"
          style={{ left: tooltip.x, top: tooltip.y - 8 }}
        >
          {tooltip.text}
        </div>
      ) : null}
    </div>
  )
}

function ArcLabel({
  arc,
  text,
  scale,
}: {
  arc: RingArc
  text: string
  scale: number
}) {
  const c = arcCentroid(arc)
  const fontSize =
    Math.min(16, (arc.outerRadius - arc.innerRadius) * 0.32) * scale
  return (
    <text
      x={c.x}
      y={c.y}
      textAnchor="middle"
      dominantBaseline="middle"
      fontSize={fontSize}
      fontWeight={600}
      fill="currentColor"
      pointerEvents="none"
      style={{ userSelect: 'none' }}
    >
      {text}
    </text>
  )
}
