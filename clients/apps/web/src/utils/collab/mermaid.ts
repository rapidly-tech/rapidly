/**
 * Clean-room Mermaid flowchart → Collab elements.
 *
 * The full Mermaid grammar is huge (state diagrams, sequence, gantt,
 * pie, er, class, journey, mindmap, gitgraph, …). This module
 * implements the **flowchart** subset that covers ~80% of real-world
 * Mermaid usage — the ""boxes and arrows"" diagrams people paste in
 * docs and chat. Out-of-scope bits are parsed past (comments, the
 * ``direction`` keyword) or simply ignored at the token level so an
 * unknown shape decays to a rectangle instead of throwing.
 *
 * What we handle
 * --------------
 *   ``flowchart TD`` / ``flowchart LR`` / ``flowchart TB`` /
 *   ``flowchart BT`` / ``flowchart RL``   — direction
 *
 *   Node shapes
 *     A[Rect]            → rect
 *     A(Rounded)         → rect + roundness
 *     A{Diamond}         → diamond
 *
 *   Edges
 *     A --> B            — arrow
 *     A --- B            — line
 *
 *   Chaining in one line: ``A --> B --> C`` → two edges.
 *
 *   ``%% comment`` lines are skipped.
 *
 * Layout
 * ------
 * Longest-path layering: every node's layer = ``max(layer(pred)) + 1``,
 * sources land at layer 0. Nodes within a layer spread uniformly along
 * the cross-axis. TD / TB / BT use vertical layers, LR / RL use
 * horizontal. Fixed node size keeps the layout crisp; users can tidy
 * up afterwards with the normal select / move tools.
 */

import type { CreateElementInput } from './element-store'

export type Direction = 'TD' | 'TB' | 'BT' | 'LR' | 'RL'

export interface MermaidNode {
  id: string
  label: string
  shape: 'rect' | 'rounded' | 'diamond'
}

export interface MermaidEdge {
  from: string
  to: string
  arrow: boolean
}

export interface MermaidDiagram {
  direction: Direction
  nodes: Map<string, MermaidNode>
  edges: MermaidEdge[]
}

/** Parse a Mermaid source string into an intermediate representation.
 *  Returns ``null`` when the input isn't a recognisable flowchart so
 *  the demo can surface a friendly error instead of inserting chaos. */
export function parseMermaid(source: string): MermaidDiagram | null {
  const lines = source.split(/\r?\n/)
  let i = 0
  // Skip blank / comment lines before the header.
  while (i < lines.length && !lines[i].trim()) i++
  const header = lines[i]?.trim() ?? ''
  const headerMatch = /^(?:flowchart|graph)\s+(TD|TB|BT|LR|RL)\b/i.exec(header)
  if (!headerMatch) return null
  const direction = headerMatch[1].toUpperCase() as Direction
  i++

  const nodes = new Map<string, MermaidNode>()
  const edges: MermaidEdge[] = []

  for (; i < lines.length; i++) {
    const line = lines[i].split('%%')[0].trim()
    if (line.length === 0) continue
    // Direction redeclaration: ``direction LR`` — update + continue.
    const dirRe = /^direction\s+(TD|TB|BT|LR|RL)$/i.exec(line)
    if (dirRe) continue
    parseStatement(line, nodes, edges)
  }

  return { direction, nodes, edges }
}

/** Parse one statement — may be a single node decl or a chain of
 *  edges like ``A --> B --> C``. Unknown syntax is silently skipped so
 *  a garbled line doesn't abort the whole parse. */
function parseStatement(
  line: string,
  nodes: Map<string, MermaidNode>,
  edges: MermaidEdge[],
): void {
  // Tokenise: node tokens + edge tokens.
  // Node token: id + optional shape wrapper.
  // Edge token: --> or ---
  const tokens = tokenise(line)
  if (tokens.length === 0) return

  // First token must be a node. Walk alternating edge / node.
  let previousNodeId: string | null = null
  let pendingArrow: boolean | null = null
  for (const tok of tokens) {
    if (tok.kind === 'node') {
      // Register node (if not already known) using either this
      // occurrence's shape info or — if none — default to rect.
      const existing = nodes.get(tok.id)
      if (tok.label !== undefined || tok.shape !== undefined) {
        nodes.set(tok.id, {
          id: tok.id,
          label: tok.label ?? existing?.label ?? tok.id,
          shape: tok.shape ?? existing?.shape ?? 'rect',
        })
      } else if (!existing) {
        nodes.set(tok.id, { id: tok.id, label: tok.id, shape: 'rect' })
      }

      if (previousNodeId !== null && pendingArrow !== null) {
        edges.push({ from: previousNodeId, to: tok.id, arrow: pendingArrow })
      }
      previousNodeId = tok.id
      pendingArrow = null
    } else {
      pendingArrow = tok.arrow
    }
  }
}

type Token =
  | { kind: 'node'; id: string; label?: string; shape?: MermaidNode['shape'] }
  | { kind: 'edge'; arrow: boolean }

/** Pull tokens out of a single statement. Simple char-by-char scan —
 *  the grammar subset is small enough that a full parser generator
 *  would be overkill. */
function tokenise(line: string): Token[] {
  const out: Token[] = []
  let i = 0
  const n = line.length
  while (i < n) {
    const ch = line[i]
    if (ch === ' ' || ch === '\t') {
      i++
      continue
    }
    // Edge: ``-->`` or ``---``.
    if (ch === '-' && line[i + 1] === '-') {
      if (line[i + 2] === '>') {
        out.push({ kind: 'edge', arrow: true })
        i += 3
        continue
      }
      if (line[i + 2] === '-') {
        out.push({ kind: 'edge', arrow: false })
        i += 3
        continue
      }
    }
    // Node: id [shape?]
    const idStart = i
    while (i < n && /[A-Za-z0-9_-]/.test(line[i])) i++
    if (i === idStart) {
      // Unknown character — skip to avoid infinite loops on garbage.
      i++
      continue
    }
    const id = line.slice(idStart, i)
    let label: string | undefined
    let shape: MermaidNode['shape'] | undefined
    const nextChar = line[i]
    if (nextChar === '[') {
      const end = line.indexOf(']', i + 1)
      if (end !== -1) {
        label = stripQuotes(line.slice(i + 1, end))
        shape = 'rect'
        i = end + 1
      }
    } else if (nextChar === '(') {
      const end = line.indexOf(')', i + 1)
      if (end !== -1) {
        label = stripQuotes(line.slice(i + 1, end))
        shape = 'rounded'
        i = end + 1
      }
    } else if (nextChar === '{') {
      const end = line.indexOf('}', i + 1)
      if (end !== -1) {
        label = stripQuotes(line.slice(i + 1, end))
        shape = 'diamond'
        i = end + 1
      }
    }
    out.push({ kind: 'node', id, label, shape })
  }
  return out
}

function stripQuotes(s: string): string {
  const t = s.trim()
  if (t.length >= 2 && t[0] === '"' && t[t.length - 1] === '"') {
    return t.slice(1, -1)
  }
  return t
}

// ── Layout + element emission ────────────────────────────────────────

const NODE_WIDTH = 160
const NODE_HEIGHT = 60
const GAP_X = 60
const GAP_Y = 60

export interface MermaidLayoutOptions {
  /** World coord for the first node's top-left. Defaults to (0, 0). */
  originX?: number
  originY?: number
}

/** Convert a parsed Mermaid diagram into ``CreateElementInput``s —
 *  ready to be ``store.create``'d in a single ``transact`` block. The
 *  second element of each edge tuple is the arrow; nodes come first
 *  so edges can bind via ``startBinding`` / ``endBinding`` without
 *  racing against a missing target at creation time. */
export function mermaidToElements(
  diagram: MermaidDiagram,
  options: MermaidLayoutOptions = {},
): CreateElementInput[] {
  const originX = options.originX ?? 0
  const originY = options.originY ?? 0

  const layers = computeLayers(diagram)
  const positions = layoutPositions(layers, diagram.direction, originX, originY)

  const out: CreateElementInput[] = []

  // Emit nodes first so arrow bindings have something to refer to.
  for (const [id, node] of diagram.nodes) {
    const pos = positions.get(id)
    if (!pos) continue
    out.push(nodeToElement(node, pos))
  }

  for (const edge of diagram.edges) {
    const from = positions.get(edge.from)
    const to = positions.get(edge.to)
    if (!from || !to) continue
    out.push(edgeToElement(edge, from, to))
  }

  return out
}

/** Longest-path layering: each node's layer = max pred layer + 1.
 *  Unreachable-from-source nodes (pure sinks with no edges at all) end
 *  up in layer 0 so they still render. */
function computeLayers(diagram: MermaidDiagram): Map<string, number> {
  const preds = new Map<string, string[]>()
  for (const id of diagram.nodes.keys()) preds.set(id, [])
  for (const e of diagram.edges) {
    if (!preds.has(e.to)) preds.set(e.to, [])
    preds.get(e.to)!.push(e.from)
  }

  const layer = new Map<string, number>()
  // Repeat until stable — small diagrams converge in ≤ |nodes|
  // iterations.
  const ids = [...diagram.nodes.keys()]
  for (let iter = 0; iter < ids.length + 1; iter++) {
    let changed = false
    for (const id of ids) {
      const predLayers = preds
        .get(id)!
        .map((p) => layer.get(p))
        .filter((n): n is number => n !== undefined)
      const next = predLayers.length === 0 ? 0 : Math.max(...predLayers) + 1
      if (layer.get(id) !== next) {
        layer.set(id, next)
        changed = true
      }
    }
    if (!changed) break
  }
  // Any node without a layer yet (cycle) gets 0.
  for (const id of ids) if (!layer.has(id)) layer.set(id, 0)
  return layer
}

/** Translate layer numbers into concrete world coords. Direction maps
 *  layer-axis = flow direction; within-layer nodes spread along the
 *  perpendicular axis. */
function layoutPositions(
  layers: Map<string, number>,
  direction: Direction,
  originX: number,
  originY: number,
): Map<string, { x: number; y: number }> {
  // Bucket nodes by layer.
  const byLayer = new Map<number, string[]>()
  for (const [id, n] of layers) {
    if (!byLayer.has(n)) byLayer.set(n, [])
    byLayer.get(n)!.push(id)
  }
  // Stable ordering — sort alphabetically so the same input always
  // produces the same layout.
  for (const bucket of byLayer.values()) bucket.sort()

  const positions = new Map<string, { x: number; y: number }>()
  const isVertical =
    direction === 'TD' || direction === 'TB' || direction === 'BT'
  const reverseLayer = direction === 'BT' || direction === 'RL'

  const layerCount = Math.max(...byLayer.keys()) + 1
  const maxLayerSize = Math.max(...[...byLayer.values()].map((b) => b.length))

  for (const [n, bucket] of byLayer) {
    const layerIndex = reverseLayer ? layerCount - 1 - n : n
    const perpTotal = bucket.length
    for (let k = 0; k < perpTotal; k++) {
      const id = bucket[k]
      // Centre each bucket so layouts look balanced regardless of
      // bucket size.
      const perpOffset = (maxLayerSize - perpTotal) / 2 + k
      if (isVertical) {
        positions.set(id, {
          x: originX + perpOffset * (NODE_WIDTH + GAP_X),
          y: originY + layerIndex * (NODE_HEIGHT + GAP_Y),
        })
      } else {
        positions.set(id, {
          x: originX + layerIndex * (NODE_WIDTH + GAP_X),
          y: originY + perpOffset * (NODE_HEIGHT + GAP_Y),
        })
      }
    }
  }

  return positions
}

function nodeToElement(
  node: MermaidNode,
  pos: { x: number; y: number },
): CreateElementInput {
  if (node.shape === 'diamond') {
    return {
      type: 'diamond',
      x: pos.x,
      y: pos.y,
      width: NODE_WIDTH,
      height: NODE_HEIGHT,
      roundness: 0,
      boundTextId: undefined,
    } as CreateElementInput
  }
  return {
    type: 'rect',
    x: pos.x,
    y: pos.y,
    width: NODE_WIDTH,
    height: NODE_HEIGHT,
    roundness: node.shape === 'rounded' ? 16 : 0,
  } as CreateElementInput
}

function edgeToElement(
  edge: MermaidEdge,
  from: { x: number; y: number },
  to: { x: number; y: number },
): CreateElementInput {
  // Connect rough centre-to-centre. Rely on the arrow-binding phase
  // (if any) to snap endpoints to perimeter slots; for now a plain
  // start / end works for vertical / horizontal layouts.
  const startX = from.x + NODE_WIDTH / 2
  const startY = from.y + NODE_HEIGHT / 2
  const endX = to.x + NODE_WIDTH / 2
  const endY = to.y + NODE_HEIGHT / 2
  return {
    type: edge.arrow ? 'arrow' : 'line',
    x: startX,
    y: startY,
    width: endX - startX,
    height: endY - startY,
    points: [0, 0, endX - startX, endY - startY],
  } as CreateElementInput
}
