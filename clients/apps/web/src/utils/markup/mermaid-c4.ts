/**
 * C4Context-diagram subset of Mermaid → Collab elements.
 *
 * Parses the Mermaid C4 syntax — nodes such as ``Person``,
 * ``System``, ``Container``, ``Component`` (plus their ``_Ext``
 * variants), boundaries (``System_Boundary``, ``Container_Boundary``,
 * ``Enterprise_Boundary``), and ``Rel`` relationships — and lays it
 * out as a left-to-right flow grouped by boundary.
 *
 * What we handle
 * --------------
 *   ``C4Context``                       — header (alias: ``C4Container``)
 *   ``title Banking Diagram``           — title
 *   ``Person(c, "Customer", "desc")``   — actors/systems/containers
 *   ``System(s, "API", "desc")``        — systems
 *   ``System_Ext(e, "Mainframe", ...)`` — external systems (rendered
 *                                         with a dashed border)
 *   ``System_Boundary(b, "Banking") {`` — boundary group (closed by
 *                                         ``}`` on its own line)
 *   ``Rel(c, s, "uses", "HTTPS")``      — directed relationship
 *   ``BiRel(a, b, "talks to")``         — bidirectional relationship
 *   ``%% comment`` lines                — skipped
 *
 * Out of scope (decays to "ignored line"):
 *   - ``UpdateRelStyle`` / ``UpdateLayoutConfig`` styling directives
 *   - sprite icons
 *   - tags / SHOW_LEGEND
 */

import type { CreateElementInput } from './element-store'

export type C4NodeKind =
  | 'Person'
  | 'PersonExt'
  | 'System'
  | 'SystemExt'
  | 'SystemDb'
  | 'Container'
  | 'ContainerExt'
  | 'ContainerDb'
  | 'Component'
  | 'ComponentExt'

export interface C4Node {
  id: string
  kind: C4NodeKind
  label: string
  description: string
  /** Boundary id this node sits inside, or `null` for top-level. */
  boundary: string | null
}

export interface C4Boundary {
  id: string
  label: string
  /** Parent boundary id, or `null` when top-level. */
  parent: string | null
}

export interface C4Rel {
  from: string
  to: string
  label: string
  technology: string
  bidirectional: boolean
}

export interface C4Diagram {
  title: string
  nodes: C4Node[]
  boundaries: C4Boundary[]
  rels: C4Rel[]
}

const NODE_KEYWORDS: Record<string, C4NodeKind> = {
  Person: 'Person',
  Person_Ext: 'PersonExt',
  System: 'System',
  System_Ext: 'SystemExt',
  SystemDb: 'SystemDb',
  SystemDb_Ext: 'SystemDb',
  Container: 'Container',
  Container_Ext: 'ContainerExt',
  ContainerDb: 'ContainerDb',
  ContainerDb_Ext: 'ContainerDb',
  Component: 'Component',
  Component_Ext: 'ComponentExt',
}

const BOUNDARY_KEYWORDS = new Set([
  'System_Boundary',
  'Container_Boundary',
  'Enterprise_Boundary',
  'Boundary',
])

/** Parse the C4 source. Returns ``null`` when the input doesn't begin
 *  with ``C4`` so the caller can fall through to the generic
 *  "unsupported kind" message. */
export function parseC4(source: string): C4Diagram | null {
  const lines = source.split(/\r?\n/)
  let i = 0
  while (i < lines.length && !lines[i].trim()) i++
  const header = lines[i]?.trim() ?? ''
  if (!/^C4(?:Context|Container|Component|Dynamic|Deployment)\b/i.test(header))
    return null
  i++

  let title = ''
  const nodes: C4Node[] = []
  const boundaries: C4Boundary[] = []
  const rels: C4Rel[] = []
  const boundaryStack: string[] = []

  for (; i < lines.length; i++) {
    const raw = lines[i].split('%%')[0].trim()
    if (raw.length === 0) continue

    if (raw === '}') {
      boundaryStack.pop()
      continue
    }

    const titleMatch = /^title\s+(.+)$/i.exec(raw)
    if (titleMatch) {
      title = titleMatch[1].trim()
      continue
    }

    // Boundary opener: ``System_Boundary(b1, "Banking") {`` (the
    // brace can sit on the same line or the next).
    const boundaryMatch = /^(\w+)\s*\(([^)]*)\)\s*\{?\s*$/.exec(raw)
    if (boundaryMatch && BOUNDARY_KEYWORDS.has(boundaryMatch[1])) {
      const args = splitArgs(boundaryMatch[2])
      const id = args[0] ?? ''
      const label = args[1] ?? ''
      if (id) {
        boundaries.push({
          id,
          label,
          parent: boundaryStack[boundaryStack.length - 1] ?? null,
        })
        boundaryStack.push(id)
      }
      continue
    }

    // Relationship: ``Rel(a, b, "uses", "HTTPS")`` — fourth arg is
    // optional. ``BiRel`` is the same with a bidirectional arrow.
    const relMatch = /^(BiRel|Rel(?:_[A-Za-z]+)?)\s*\(([^)]*)\)\s*$/.exec(raw)
    if (relMatch) {
      const args = splitArgs(relMatch[2])
      if (args.length >= 2) {
        rels.push({
          from: args[0],
          to: args[1],
          label: args[2] ?? '',
          technology: args[3] ?? '',
          bidirectional: relMatch[1] === 'BiRel',
        })
      }
      continue
    }

    // Node: ``Person(c, "Customer", "desc")`` etc.
    const nodeMatch = /^(\w+)\s*\(([^)]*)\)\s*$/.exec(raw)
    if (nodeMatch) {
      const kind = NODE_KEYWORDS[nodeMatch[1]]
      if (kind) {
        const args = splitArgs(nodeMatch[2])
        const id = args[0] ?? ''
        if (id) {
          nodes.push({
            id,
            kind,
            label: args[1] ?? '',
            description: args[2] ?? '',
            boundary: boundaryStack[boundaryStack.length - 1] ?? null,
          })
        }
      }
      continue
    }
    // Unrecognised — silently skip.
  }

  return { title, nodes, boundaries, rels }
}

/** Comma-split that respects double-quoted strings so labels with
 *  commas survive. Quotes are stripped from the result. */
function splitArgs(s: string): string[] {
  const out: string[] = []
  let buf = ''
  let inQuote = false
  for (let i = 0; i < s.length; i++) {
    const c = s[i]
    if (c === '"') {
      inQuote = !inQuote
      continue
    }
    if (c === ',' && !inQuote) {
      out.push(buf.trim())
      buf = ''
      continue
    }
    buf += c
  }
  if (buf.trim().length > 0 || out.length > 0) out.push(buf.trim())
  return out
}

const NODE_W = 180
const NODE_H = 90
const NODE_GAP_X = 60
const NODE_GAP_Y = 40
const BOUNDARY_PAD = 24
const TITLE_HEIGHT = 28

export interface C4LayoutOptions {
  originX?: number
  originY?: number
}

/** Lay out the parsed diagram and emit Collab element inputs. Nodes
 *  inside the same boundary share a row; boundaries stack vertically;
 *  rels are drawn as straight arrows between node centres. */
export function c4ToElements(
  diagram: C4Diagram,
  options: C4LayoutOptions = {},
): CreateElementInput[] {
  const ox = options.originX ?? 0
  const oy = options.originY ?? 0
  const out: CreateElementInput[] = []

  if (diagram.nodes.length === 0 && diagram.boundaries.length === 0) {
    if (diagram.title) {
      out.push(makeTitle(diagram.title, ox, oy))
    }
    return out
  }

  let cursorY = oy
  if (diagram.title) {
    out.push(makeTitle(diagram.title, ox, cursorY))
    cursorY += TITLE_HEIGHT
  }

  // Group nodes by boundary id (or `null` for top-level).
  const groups = new Map<string | null, C4Node[]>()
  for (const n of diagram.nodes) {
    const key = n.boundary
    if (!groups.has(key)) groups.set(key, [])
    groups.get(key)!.push(n)
  }

  // Render groups in declaration order: top-level first, then each
  // boundary in the order it appeared. Stable so collab peers agree.
  const groupOrder: Array<string | null> = []
  if (groups.has(null)) groupOrder.push(null)
  for (const b of diagram.boundaries) {
    if (groups.has(b.id)) groupOrder.push(b.id)
  }

  // Track each node's centre so rels can connect them.
  const centres = new Map<string, { x: number; y: number }>()

  for (const key of groupOrder) {
    const groupNodes = groups.get(key)!
    const boundary = key
      ? diagram.boundaries.find((b) => b.id === key)
      : undefined

    const rowY = cursorY + (boundary ? BOUNDARY_PAD : 0)
    const totalW =
      groupNodes.length * NODE_W + (groupNodes.length - 1) * NODE_GAP_X
    const startX = ox + (boundary ? BOUNDARY_PAD : 0)

    // Boundary rect first so it sits behind the nodes.
    if (boundary) {
      const bx = ox
      const by = cursorY
      const bw = totalW + 2 * BOUNDARY_PAD
      const bh = NODE_H + 2 * BOUNDARY_PAD + 18
      out.push({
        type: 'rect',
        x: bx,
        y: by,
        width: bw,
        height: bh,
        strokeColor: '#475569',
        fillColor: 'transparent',
        fillStyle: 'none',
        strokeWidth: 1,
        strokeStyle: 'dashed',
        roughness: 0,
        opacity: 100,
        seed: hash(`c4-boundary-${boundary.id}`),
        version: 0,
        locked: false,
        angle: 0,
        zIndex: 0,
        groupIds: [],
        roundness: 1,
      } as CreateElementInput)
      // Boundary label in the top-left.
      out.push({
        type: 'text',
        x: bx + 8,
        y: by + 4,
        width: bw - 16,
        height: 14,
        text: boundary.label || boundary.id,
        fontFamily: 'sans',
        fontSize: 11,
        fontWeight: 'bold',
        textAlign: 'left',
        strokeColor: '#475569',
        fillColor: 'transparent',
        fillStyle: 'none',
        strokeWidth: 1,
        strokeStyle: 'solid',
        roughness: 0,
        opacity: 100,
        seed: hash(`c4-boundary-label-${boundary.id}`),
        version: 0,
        locked: false,
        angle: 0,
        zIndex: 0,
        groupIds: [],
      } as CreateElementInput)
    }

    groupNodes.forEach((node, idx) => {
      const nx = startX + idx * (NODE_W + NODE_GAP_X)
      const ny = rowY + (boundary ? 18 : 0)
      const fill = pickFill(node.kind)
      const isExternal =
        node.kind === 'PersonExt' ||
        node.kind === 'SystemExt' ||
        node.kind === 'ContainerExt' ||
        node.kind === 'ComponentExt'
      out.push({
        type: 'rect',
        x: nx,
        y: ny,
        width: NODE_W,
        height: NODE_H,
        strokeColor: '#1e1e1e',
        fillColor: fill,
        fillStyle: 'solid',
        strokeWidth: isExternal ? 2 : 1,
        strokeStyle: isExternal ? 'dashed' : 'solid',
        roughness: 0,
        opacity: 100,
        seed: hash(`c4-node-${node.id}`),
        version: 0,
        locked: false,
        angle: 0,
        zIndex: 0,
        groupIds: [],
        roundness: 2,
      } as CreateElementInput)

      // Kind tag — small italicised line at the top of the box.
      out.push({
        type: 'text',
        x: nx + 6,
        y: ny + 6,
        width: NODE_W - 12,
        height: 12,
        text: `«${kindTag(node.kind)}»`,
        fontFamily: 'sans',
        fontSize: 9,
        textAlign: 'center',
        strokeColor: '#475569',
        fillColor: 'transparent',
        fillStyle: 'none',
        strokeWidth: 1,
        strokeStyle: 'solid',
        roughness: 0,
        opacity: 100,
        seed: hash(`c4-kind-${node.id}`),
        version: 0,
        locked: false,
        angle: 0,
        zIndex: 0,
        groupIds: [],
      } as CreateElementInput)
      // Label.
      out.push({
        type: 'text',
        x: nx + 6,
        y: ny + 22,
        width: NODE_W - 12,
        height: 16,
        text: node.label || node.id,
        fontFamily: 'sans',
        fontSize: 12,
        fontWeight: 'bold',
        textAlign: 'center',
        strokeColor: '#1e1e1e',
        fillColor: 'transparent',
        fillStyle: 'none',
        strokeWidth: 1,
        strokeStyle: 'solid',
        roughness: 0,
        opacity: 100,
        seed: hash(`c4-label-${node.id}`),
        version: 0,
        locked: false,
        angle: 0,
        zIndex: 0,
        groupIds: [],
      } as CreateElementInput)
      // Description (wraps to ~3 lines).
      if (node.description) {
        out.push({
          type: 'text',
          x: nx + 6,
          y: ny + 42,
          width: NODE_W - 12,
          height: 40,
          text: node.description,
          fontFamily: 'sans',
          fontSize: 10,
          textAlign: 'center',
          strokeColor: '#1e1e1e',
          fillColor: 'transparent',
          fillStyle: 'none',
          strokeWidth: 1,
          strokeStyle: 'solid',
          roughness: 0,
          opacity: 100,
          seed: hash(`c4-desc-${node.id}`),
          version: 0,
          locked: false,
          angle: 0,
          zIndex: 0,
          groupIds: [],
        } as CreateElementInput)
      }

      centres.set(node.id, { x: nx + NODE_W / 2, y: ny + NODE_H / 2 })
    })

    cursorY =
      rowY +
      (boundary ? 18 : 0) +
      NODE_H +
      (boundary ? BOUNDARY_PAD : 0) +
      NODE_GAP_Y
  }

  // Rels — straight arrows between centres. Skip rels referencing
  // nodes we never resolved.
  for (const rel of diagram.rels) {
    const a = centres.get(rel.from)
    const b = centres.get(rel.to)
    if (!a || !b) continue
    const labelText = rel.technology
      ? `${rel.label} [${rel.technology}]`
      : rel.label
    out.push({
      type: 'arrow',
      x: a.x,
      y: a.y,
      width: b.x - a.x,
      height: b.y - a.y,
      points: [0, 0, b.x - a.x, b.y - a.y],
      strokeColor: '#1e1e1e',
      fillColor: 'transparent',
      fillStyle: 'none',
      strokeWidth: 1,
      strokeStyle: 'solid',
      roughness: 0,
      opacity: 100,
      seed: hash(`c4-rel-${rel.from}-${rel.to}`),
      version: 0,
      locked: false,
      angle: 0,
      zIndex: 0,
      groupIds: [],
      startArrowhead: rel.bidirectional ? 'arrow' : null,
      endArrowhead: 'arrow',
    } as CreateElementInput)
    if (labelText) {
      out.push({
        type: 'text',
        x: Math.min(a.x, b.x),
        y: (a.y + b.y) / 2 - 8,
        width: Math.abs(b.x - a.x) || 80,
        height: 14,
        text: labelText,
        fontFamily: 'sans',
        fontSize: 10,
        textAlign: 'center',
        strokeColor: '#475569',
        fillColor: 'transparent',
        fillStyle: 'none',
        strokeWidth: 1,
        strokeStyle: 'solid',
        roughness: 0,
        opacity: 100,
        seed: hash(`c4-rel-label-${rel.from}-${rel.to}`),
        version: 0,
        locked: false,
        angle: 0,
        zIndex: 0,
        groupIds: [],
      } as CreateElementInput)
    }
  }

  return out
}

function makeTitle(text: string, ox: number, oy: number): CreateElementInput {
  return {
    type: 'text',
    x: ox,
    y: oy,
    width: 480,
    height: TITLE_HEIGHT - 6,
    text,
    fontFamily: 'sans',
    fontSize: 16,
    textAlign: 'center',
    fontWeight: 'bold',
    strokeColor: '#1e1e1e',
    fillColor: 'transparent',
    fillStyle: 'none',
    strokeWidth: 1,
    strokeStyle: 'solid',
    roughness: 0,
    opacity: 100,
    seed: hash('c4-title'),
    version: 0,
    locked: false,
    angle: 0,
    zIndex: 0,
    groupIds: [],
  } as CreateElementInput
}

function kindTag(k: C4NodeKind): string {
  switch (k) {
    case 'Person':
      return 'Person'
    case 'PersonExt':
      return 'Person, External'
    case 'System':
      return 'System'
    case 'SystemExt':
      return 'System, External'
    case 'SystemDb':
      return 'Database'
    case 'Container':
      return 'Container'
    case 'ContainerExt':
      return 'Container, External'
    case 'ContainerDb':
      return 'Database Container'
    case 'Component':
      return 'Component'
    case 'ComponentExt':
      return 'Component, External'
  }
}

function pickFill(kind: C4NodeKind): string {
  switch (kind) {
    case 'Person':
    case 'PersonExt':
      return '#a5d8ff'
    case 'System':
    case 'SystemExt':
      return '#b2f2bb'
    case 'SystemDb':
    case 'ContainerDb':
      return '#ffec99'
    case 'Container':
    case 'ContainerExt':
      return '#ffd8a8'
    case 'Component':
    case 'ComponentExt':
      return '#e0a9f0'
  }
}

function hash(s: string): number {
  let h = 5381
  for (let i = 0; i < s.length; i++) h = (h * 33) ^ s.charCodeAt(i)
  return h >>> 0
}
