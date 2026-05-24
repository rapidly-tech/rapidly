/**
 * Mindmap subset of Mermaid → Collab elements.
 *
 * Parses the indentation-based mindmap syntax and lays out the
 * hierarchy radially: the root sits at the centre, first-level
 * children fan out around it, and each subtree's descendants spread
 * within the angular sector their parent owns.
 *
 * What we handle
 * --------------
 *   ``mindmap``                       — header
 *   ``root((Centre))``                — root with circular shape
 *   ``Branch A``                      — child node (default rounded rect)
 *   ``Sub A1``                          — grandchild (extra indent)
 *   ``[Squared label]``               — rect-shape node
 *   ``(Rounded label)``               — rounded-rect node
 *   ``((Cloud label))``               — circle-shape node
 *   ``%% comment`` lines              — skipped
 *
 * Indentation is taken from leading whitespace; any consistent
 * indent step is fine because we infer the depth from the indent's
 * sort order rather than counting fixed columns.
 *
 * Out of scope (decays to default-shape rendering):
 *   - icons (``::icon(fa fa-book)``)
 *   - per-node CSS classes
 *   - markdown formatting in labels
 *   - explicit ``id[Label]`` form
 */

import type { CreateElementInput } from './element-store'

export type MindmapShape = 'circle' | 'rect' | 'rounded' | 'default'

export interface MindmapNode {
  id: number
  label: string
  shape: MindmapShape
  depth: number
  children: MindmapNode[]
}

export interface MindmapDiagram {
  /** Root node of the tree, or ``null`` when the source had no
   *  parseable nodes. */
  root: MindmapNode | null
  /** Total node count (including root) — handy for layout sanity
   *  bounds. */
  nodeCount: number
}

/** Parse the mindmap source. Returns ``null`` when the input doesn't
 *  begin with ``mindmap`` so the caller can fall through to the
 *  generic "unsupported kind" message. */
export function parseMindmap(source: string): MindmapDiagram | null {
  const lines = source.split(/\r?\n/)
  let i = 0
  while (i < lines.length && !lines[i].trim()) i++
  const header = lines[i]?.trim() ?? ''
  if (!/^mindmap\b/i.test(header)) return null
  i++

  // First pass: extract every non-empty, non-comment line with its
  // leading-indent length. Lines with the smallest indent are the
  // shallowest; the indent values themselves don't have to be
  // consistent because we sort uniquely-seen indents into a depth
  // ranking.
  interface RawLine {
    indent: number
    text: string
  }
  const raw: RawLine[] = []
  for (; i < lines.length; i++) {
    const line = lines[i].split('%%')[0]
    const trimmed = line.trim()
    if (trimmed.length === 0) continue
    const indent = line.length - line.trimStart().length
    raw.push({ indent, text: trimmed })
  }
  if (raw.length === 0) {
    return { root: null, nodeCount: 0 }
  }

  // Map each unique indent value to a depth (0..N). The smallest
  // indent → depth 0 (the root level), next → depth 1, etc.
  const uniqueIndents = Array.from(new Set(raw.map((r) => r.indent))).sort(
    (a, b) => a - b,
  )
  const depthOf = new Map<number, number>()
  uniqueIndents.forEach((indent, depth) => depthOf.set(indent, depth))

  // Second pass: build the tree using a stack. The stack holds the
  // current ancestor at each depth; pushing a node at depth D pops
  // every entry deeper than D-1, then attaches the new node to the
  // entry at D-1.
  let nodeId = 0
  const root: MindmapNode | null = null
  const stack: MindmapNode[] = []
  let actualRoot: MindmapNode | null = null

  for (const r of raw) {
    const depth = depthOf.get(r.indent) ?? 0
    const { label, shape } = parseShape(r.text)
    const node: MindmapNode = {
      id: nodeId++,
      label,
      shape,
      depth,
      children: [],
    }
    if (depth === 0) {
      // Top-level entry. Mermaid usually has exactly one but we
      // gracefully handle multiple by re-anchoring the synthetic
      // root.
      if (!actualRoot) {
        actualRoot = node
      } else {
        // Multiple depth-0 nodes — promote the existing root into a
        // synthetic "Mindmap" root and reparent. Rare in practice.
        if (actualRoot.label !== 'Mindmap' || actualRoot.id !== -1) {
          const synthetic: MindmapNode = {
            id: -1,
            label: 'Mindmap',
            shape: 'circle',
            depth: -1,
            children: [actualRoot, node],
          }
          actualRoot = synthetic
        } else {
          actualRoot.children.push(node)
        }
      }
      stack.length = 0
      stack[0] = node
      continue
    }
    // Pop the stack until we find an ancestor at depth - 1.
    while (stack.length > depth) stack.pop()
    const parent = stack[depth - 1]
    if (parent) parent.children.push(node)
    stack[depth] = node
  }

  return {
    root: actualRoot ?? root,
    nodeCount: nodeId,
  }
}

/** Strip the wrapping shape tokens off a node label and return the
 *  recognised ``MindmapShape``. Defaults to ``default`` (a plain
 *  rounded rect with no special rendering) for any unknown form.
 *
 *  Also strips the leading ``root`` keyword if present — Mermaid
 *  uses ``root((Centre))`` to mark the root node, but the ``root``
 *  word itself isn't part of the label. */
function parseShape(text: string): { label: string; shape: MindmapShape } {
  // Drop a leading ``root`` keyword; the shape tokens that follow
  // (or the bare label) are what we actually parse.
  const stripped = text.replace(/^root\s*/, '')
  // Order matters — match the longest opening token first so
  // ``((x))`` doesn't get caught as ``(x)``.
  const cloud = /^\(\((.+)\)\)$/.exec(stripped)
  if (cloud) return { label: cloud[1].trim(), shape: 'circle' }
  const rect = /^\[(.+)\]$/.exec(stripped)
  if (rect) return { label: rect[1].trim(), shape: 'rect' }
  const rounded = /^\((.+)\)$/.exec(stripped)
  if (rounded) return { label: rounded[1].trim(), shape: 'rounded' }
  // Bare ``root`` with no shape token gets ``Root`` as a friendly
  // default label so the centre node still has something to display.
  if (stripped.length === 0) return { label: 'Root', shape: 'circle' }
  return { label: stripped, shape: 'default' }
}

const NODE_WIDTH = 140
const NODE_HEIGHT = 40
const ROOT_RADIUS = 60
const RING_GAP = 90 // distance between successive ring radii

export interface MindmapLayoutOptions {
  originX?: number
  originY?: number
}

/** Lay the parsed tree out radially and emit Collab element inputs.
 *
 *  Each depth gets a ring; nodes are placed at angles within the
 *  angular sector their parent owns. The root sits at the centre
 *  of the layout with a special circle shape. */
export function mindmapToElements(
  diagram: MindmapDiagram,
  options: MindmapLayoutOptions = {},
): CreateElementInput[] {
  if (!diagram.root) return []
  const ox = options.originX ?? 0
  const oy = options.originY ?? 0
  const out: CreateElementInput[] = []

  // Centre of the layout — use ``originX/Y`` as the centre rather
  // than the top-left so the radial spread is symmetric.
  const cx = ox
  const cy = oy

  // Recursive walk. Each call places the node at (cx, cy) +
  // (cos*r, sin*r) and recurses into children, dividing the
  // remaining angular sector evenly.
  interface Placed {
    node: MindmapNode
    x: number
    y: number
  }
  const placed = new Map<number, Placed>()

  const walk = (
    node: MindmapNode,
    depth: number,
    angle: number,
    sector: number,
  ): void => {
    let x: number
    let y: number
    if (depth === 0) {
      x = cx
      y = cy
    } else {
      const r = depth * RING_GAP
      x = cx + Math.cos(angle) * r
      y = cy + Math.sin(angle) * r
    }
    placed.set(node.id, { node, x, y })

    if (node.children.length === 0) return
    // Divide the parent's sector evenly across children. At depth 0
    // the sector is the full circle (2π) so children spread all
    // around; at depth 1+ the sector is what the parent received.
    const childSector =
      depth === 0
        ? (Math.PI * 2) / node.children.length
        : sector / node.children.length
    const startAngle =
      depth === 0 ? -Math.PI / 2 : angle - sector / 2 + childSector / 2
    node.children.forEach((child, idx) => {
      const childAngle = startAngle + idx * childSector
      walk(child, depth + 1, childAngle, childSector)
    })
  }
  walk(diagram.root, 0, 0, Math.PI * 2)

  // Emit nodes (root first so the connectors paint on top).
  for (const p of placed.values()) {
    out.push(...nodeToElements(p))
  }
  // Emit connectors — line from each child back to its parent.
  emitConnectors(diagram.root, placed, out)

  return out
}

function nodeToElements(p: {
  node: MindmapNode
  x: number
  y: number
}): CreateElementInput[] {
  const els: CreateElementInput[] = []
  const isRoot = p.node.depth === 0
  const w = isRoot ? ROOT_RADIUS * 2 : NODE_WIDTH
  const h = isRoot ? ROOT_RADIUS * 2 : NODE_HEIGHT
  const x = p.x - w / 2
  const y = p.y - h / 2
  // Background shape.
  if (isRoot || p.node.shape === 'circle') {
    els.push({
      type: 'ellipse',
      x,
      y,
      width: w,
      height: h,
      strokeColor: '#1e1e1e',
      fillColor: isRoot ? '#fef3c7' : '#fff7ed',
      fillStyle: 'solid',
      strokeWidth: 1,
      strokeStyle: 'solid',
      roughness: 0,
      opacity: 100,
      seed: hash(`mm-node-${p.node.id}`),
      version: 0,
      locked: false,
      angle: 0,
      zIndex: 0,
      groupIds: [],
    } as CreateElementInput)
  } else {
    els.push({
      type: 'rect',
      x,
      y,
      width: w,
      height: h,
      strokeColor: '#1e1e1e',
      fillColor: '#f8fafc',
      fillStyle: 'solid',
      strokeWidth: 1,
      strokeStyle: 'solid',
      roughness: 0,
      opacity: 100,
      seed: hash(`mm-node-${p.node.id}`),
      version: 0,
      locked: false,
      angle: 0,
      zIndex: 0,
      groupIds: [],
      // Shape tokens map to roundness: rect → 0 (sharp), rounded
      // and default → 16 (round).
      roundness: p.node.shape === 'rect' ? 0 : 16,
    } as CreateElementInput)
  }
  // Label.
  els.push({
    type: 'text',
    x: x + 6,
    y: p.y - 9,
    width: w - 12,
    height: 18,
    text: p.node.label,
    fontFamily: 'sans',
    fontSize: isRoot ? 16 : 13,
    textAlign: 'center',
    fontWeight: isRoot ? 'bold' : 'normal',
    strokeColor: '#1e1e1e',
    fillColor: 'transparent',
    fillStyle: 'none',
    strokeWidth: 1,
    strokeStyle: 'solid',
    roughness: 0,
    opacity: 100,
    seed: hash(`mm-label-${p.node.id}`),
    version: 0,
    locked: false,
    angle: 0,
    zIndex: 0,
    groupIds: [],
  } as CreateElementInput)
  return els
}

function emitConnectors(
  node: MindmapNode,
  placed: Map<number, { node: MindmapNode; x: number; y: number }>,
  out: CreateElementInput[],
): void {
  const me = placed.get(node.id)
  if (!me) return
  for (const child of node.children) {
    const c = placed.get(child.id)
    if (!c) continue
    const minX = Math.min(me.x, c.x)
    const minY = Math.min(me.y, c.y)
    out.push({
      type: 'line',
      x: minX,
      y: minY,
      width: Math.abs(c.x - me.x),
      height: Math.abs(c.y - me.y),
      points: [me.x - minX, me.y - minY, c.x - minX, c.y - minY],
      strokeColor: '#94a3b8',
      fillColor: 'transparent',
      fillStyle: 'none',
      strokeWidth: 1,
      strokeStyle: 'solid',
      roughness: 0,
      opacity: 100,
      seed: hash(`mm-connector-${node.id}-${child.id}`),
      version: 0,
      locked: false,
      angle: 0,
      zIndex: 0,
      groupIds: [],
    } as CreateElementInput)
    emitConnectors(child, placed, out)
  }
}

function hash(s: string): number {
  let h = 5381
  for (let i = 0; i < s.length; i++) h = (h * 33) ^ s.charCodeAt(i)
  return h >>> 0
}
