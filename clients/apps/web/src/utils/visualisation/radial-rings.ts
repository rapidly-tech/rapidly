/**
 * Radial-rings layout — pure helpers that turn a tree of nodes into
 * concentric annular ring segments suitable for SVG ``<path>`` paint.
 *
 * The model:
 *   - A ``RingNode`` is any tree node ``{ id, label?, value?, color?,
 *     children? }``.
 *   - Each leaf carries a ``value``; internal nodes inherit the sum
 *     of their descendants.
 *   - The root spans the full circle (``0`` to ``2π``).
 *   - Children are partitioned into adjacent angular slices
 *     proportional to their summed value.
 *   - Depth maps to a radial band: depth 0 is the centre disc, each
 *     deeper layer sits in a thinner outer ring (``radiusScaleExponent``
 *     controls how quickly thickness shrinks; ``0.5`` keeps arc area
 *     proportional to value).
 *
 * Output is a flat list of ``RingArc`` records — one per node — that a
 * React component can map straight to SVG paths via ``arcPath``.
 *
 * Pure / deterministic / no DOM. The visible component lives at
 * ``components/Revolver/RadialRings.tsx``.
 */

export interface RingNode {
  id: string
  label?: string
  /** Required on leaves. Internal nodes derive their value from
   *  ``sum(children.value)``; an explicit value on a non-leaf is
   *  ignored so the tree stays consistent. */
  value?: number
  color?: string
  children?: RingNode[]
}

export interface RingArc {
  id: string
  /** 0 = centre disc, 1 = first ring, … */
  depth: number
  label: string
  color: string
  value: number
  /** Inclusive at start, exclusive at end. Radians, 0 = 12 o'clock,
   *  growing clockwise — matches the SVG convention used by ``arcPath``. */
  startAngle: number
  endAngle: number
  innerRadius: number
  outerRadius: number
}

export interface LayoutOptions {
  /** Outer radius the deepest ring should reach. */
  radius: number
  /** Fraction of ``radius`` reserved for the centre disc. */
  centerRadius?: number
  /** Power applied to the linear depth ratio when computing each
   *  ring's inner/outer radius. ``0.5`` (default) keeps arc area
   *  proportional to value across depths; ``1`` produces equal-
   *  thickness bands. */
  radiusScaleExponent?: number
  /** Default fill colour for nodes that don't carry their own. */
  defaultColor?: string
}

const DEFAULT_CENTER_RADIUS = 0.1
const DEFAULT_RADIUS_SCALE = 0.5
const DEFAULT_COLOR = '#94a3b8'
const TWO_PI = Math.PI * 2

/** Walk the tree, computing every node's ring arc. The returned list
 *  is in pre-order (parents before children) so a React paint-order
 *  iteration draws the centre first. */
export function layoutRingTree(
  root: RingNode,
  options: LayoutOptions,
): RingArc[] {
  const radius = options.radius
  const centerRadius = (options.centerRadius ?? DEFAULT_CENTER_RADIUS) * radius
  const exponent = options.radiusScaleExponent ?? DEFAULT_RADIUS_SCALE
  const defaultColor = options.defaultColor ?? DEFAULT_COLOR

  const depthOf = treeDepth(root)
  // The tree has ``depthOf + 1`` layers (root at depth 0 plus
  // ``depthOf`` rings below). Map each layer boundary i ∈ [0,
  // depthOf+1] onto a radius via ``t = i / (depthOf+1)`` so every
  // depth gets a distinct band — including the leaves, which would
  // collapse to zero thickness if we divided by ``depthOf``.
  const layers = depthOf + 1
  const radiusAt = (d: number): number => {
    if (d <= 0) return centerRadius
    if (layers <= 0) return radius
    const t = Math.min(1, d / layers)
    return centerRadius + (radius - centerRadius) * Math.pow(t, exponent)
  }

  // Pre-walk: compute summed values bottom-up.
  const totals = new Map<string, number>()
  const sumValues = (n: RingNode): number => {
    if (!n.children || n.children.length === 0) {
      const v = Math.max(0, n.value ?? 0)
      totals.set(n.id, v)
      return v
    }
    let s = 0
    for (const c of n.children) s += sumValues(c)
    totals.set(n.id, s)
    return s
  }
  sumValues(root)

  const out: RingArc[] = []
  const walk = (
    node: RingNode,
    depth: number,
    startAngle: number,
    endAngle: number,
  ): void => {
    const innerRadius = radiusAt(depth)
    const outerRadius = radiusAt(depth + 1)
    const total = totals.get(node.id) ?? 0
    out.push({
      id: node.id,
      depth,
      label: node.label ?? node.id,
      color: node.color ?? defaultColor,
      value: total,
      startAngle,
      endAngle,
      innerRadius,
      outerRadius,
    })
    if (!node.children || node.children.length === 0) return
    if (total <= 0) return
    let cursor = startAngle
    const sweep = endAngle - startAngle
    for (const child of node.children) {
      const childTotal = totals.get(child.id) ?? 0
      const childSweep = (childTotal / total) * sweep
      walk(child, depth + 1, cursor, cursor + childSweep)
      cursor += childSweep
    }
  }
  walk(root, 0, 0, TWO_PI)
  return out
}

/** Maximum depth (root = 0). */
export function treeDepth(node: RingNode): number {
  if (!node.children || node.children.length === 0) return 0
  let max = 0
  for (const c of node.children) {
    const d = treeDepth(c)
    if (d > max) max = d
  }
  return max + 1
}

/** SVG ``d`` attribute for a single annular segment, anchored at the
 *  origin. Caller positions the SVG so (0, 0) is the chart centre.
 *
 *  Uses the standard four-point construction:
 *    M  P0   (outer-arc start)
 *    A  outer-arc to P1
 *    L  P2   (radial line in to inner-arc start)
 *    A  inner-arc back to P3 (sweep reversed)
 *    Z  close
 *
 *  Angle 0 is at 12 o'clock and grows clockwise so the result lines
 *  up with the conventional clock-face reading callers expect. */
export function arcPath(arc: {
  innerRadius: number
  outerRadius: number
  startAngle: number
  endAngle: number
}): string {
  const { innerRadius, outerRadius, startAngle, endAngle } = arc
  const sweep = endAngle - startAngle
  // Full-circle annulus needs a special path — a single arc command
  // can't traverse 360° in SVG. We emit two half-circle arcs.
  if (sweep >= TWO_PI - 1e-6) {
    const r = outerRadius
    const ir = innerRadius
    return [
      `M 0 ${-r}`,
      `A ${r} ${r} 0 1 1 0 ${r}`,
      `A ${r} ${r} 0 1 1 0 ${-r}`,
      `M 0 ${-ir}`,
      `A ${ir} ${ir} 0 1 0 0 ${ir}`,
      `A ${ir} ${ir} 0 1 0 0 ${-ir}`,
      'Z',
    ].join(' ')
  }
  // Inner disc (no inner radius) — a wedge, not an annulus.
  if (innerRadius <= 1e-6) {
    const p0 = polar(outerRadius, startAngle)
    const p1 = polar(outerRadius, endAngle)
    const largeArc = sweep > Math.PI ? 1 : 0
    return [
      `M 0 0`,
      `L ${p0.x} ${p0.y}`,
      `A ${outerRadius} ${outerRadius} 0 ${largeArc} 1 ${p1.x} ${p1.y}`,
      'Z',
    ].join(' ')
  }
  // General annular segment.
  const p0 = polar(outerRadius, startAngle)
  const p1 = polar(outerRadius, endAngle)
  const p2 = polar(innerRadius, endAngle)
  const p3 = polar(innerRadius, startAngle)
  const largeArc = sweep > Math.PI ? 1 : 0
  return [
    `M ${p0.x} ${p0.y}`,
    `A ${outerRadius} ${outerRadius} 0 ${largeArc} 1 ${p1.x} ${p1.y}`,
    `L ${p2.x} ${p2.y}`,
    `A ${innerRadius} ${innerRadius} 0 ${largeArc} 0 ${p3.x} ${p3.y}`,
    'Z',
  ].join(' ')
}

/** Convert a polar (radius, angle) to a Cartesian point with angle 0
 *  at 12 o'clock and growing clockwise. */
function polar(r: number, angle: number): { x: number; y: number } {
  return {
    x: r * Math.sin(angle),
    y: -r * Math.cos(angle),
  }
}

/** Centroid (in Cartesian coords) of an annular segment — useful for
 *  positioning labels. Caller picks whether to anchor angularly or
 *  radially; we just give the geometric centre. */
export function arcCentroid(arc: {
  innerRadius: number
  outerRadius: number
  startAngle: number
  endAngle: number
}): { x: number; y: number } {
  const r = (arc.innerRadius + arc.outerRadius) / 2
  const a = (arc.startAngle + arc.endAngle) / 2
  return polar(r, a)
}
