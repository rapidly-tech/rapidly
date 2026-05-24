/**
 * Sankey-diagram subset of Mermaid → Collab elements.
 *
 * Parses the Mermaid sankey-beta syntax — a CSV body of
 * ``source,target,value`` rows after the header — and lays it out
 * as columns of node bars (sized by total flow) connected by
 * weighted lines whose stroke width is proportional to the value
 * of each link.
 *
 * What we handle
 * --------------
 *   ``sankey-beta``                         — header (alias: ``sankey``)
 *   ``A,B,10``                              — link row
 *   ``"Source",Target,5``                   — quoted node names
 *   ``%% comment`` lines                    — skipped (CSV header
 *                                             ``source,target,value``
 *                                             also skipped if present)
 *
 * Out of scope (decays to "ignored line"):
 *   - per-node colour overrides
 *   - cyclic flows (handled by a depth cap so they don't recurse
 *     forever, but the resulting layout puts the offending node at
 *     column 0)
 *   - explicit column / linkAlignment configuration
 */

import type { CreateElementInput } from './element-store'

export interface SankeyLink {
  source: string
  target: string
  value: number
}

export interface SankeyNode {
  id: string
  /** Sum of every value flowing in. */
  inflow: number
  /** Sum of every value flowing out. */
  outflow: number
  /** Larger of inflow / outflow — used as the bar's "size" so a
   *  pass-through node renders the same height as a pure source or
   *  pure sink with the same throughput. */
  size: number
  /** Column index from the longest-path layering. */
  column: number
}

export interface SankeyDiagram {
  links: SankeyLink[]
  nodes: SankeyNode[]
}

/** Parse the sankey source. Returns ``null`` when the input doesn't
 *  begin with ``sankey`` (or ``sankey-beta``) so the caller can fall
 *  through to the generic "unsupported kind" message. */
export function parseSankey(source: string): SankeyDiagram | null {
  const lines = source.split(/\r?\n/)
  let i = 0
  while (i < lines.length && !lines[i].trim()) i++
  const header = lines[i]?.trim() ?? ''
  if (!/^sankey(?:-beta)?\b/i.test(header)) return null
  i++

  const links: SankeyLink[] = []

  for (; i < lines.length; i++) {
    const raw = lines[i]
    const line = raw.split('%%')[0].trim()
    if (line.length === 0) continue

    // CSV header row that some authors include — skip silently.
    if (/^source\s*,\s*target\s*,\s*value$/i.test(line)) continue

    // Three-field CSV. Quoted fields are stripped of their wrapping
    // quotes; numeric value must be parseable.
    const fields = parseCsvRow(line)
    if (fields.length < 3) continue
    const [src, tgt, valueStr] = fields
    const value = Number(valueStr)
    if (!Number.isFinite(value) || value <= 0) continue
    links.push({ source: src, target: tgt, value })
  }

  // Build the node table from the unique source/target ids in the
  // links. Compute inflow + outflow per node + the longest-path
  // column index.
  const nodeMap = new Map<string, SankeyNode>()
  const ensure = (id: string): SankeyNode => {
    let n = nodeMap.get(id)
    if (!n) {
      n = { id, inflow: 0, outflow: 0, size: 0, column: 0 }
      nodeMap.set(id, n)
    }
    return n
  }
  for (const l of links) {
    ensure(l.source).outflow += l.value
    ensure(l.target).inflow += l.value
  }
  for (const n of nodeMap.values()) {
    n.size = Math.max(n.inflow, n.outflow)
  }

  // Longest-path columning. Predecessor map for the recursion.
  const preds = new Map<string, string[]>()
  for (const id of nodeMap.keys()) preds.set(id, [])
  for (const l of links) preds.get(l.target)?.push(l.source)
  const visiting = new Set<string>()
  const maxDepth = nodeMap.size
  const colOf = (id: string, depth: number): number => {
    if (depth > maxDepth) return 0
    const node = nodeMap.get(id)
    if (!node) return 0
    if (visiting.has(id)) return 0
    visiting.add(id)
    const ps = preds.get(id) ?? []
    let max = -1
    for (const p of ps) {
      const pc = colOf(p, depth + 1)
      if (pc > max) max = pc
    }
    visiting.delete(id)
    node.column = max + 1
    return node.column
  }
  for (const id of nodeMap.keys()) colOf(id, 0)

  return { links, nodes: Array.from(nodeMap.values()) }
}

/** Parse a single CSV row, honouring double-quoted fields. Mermaid
 *  doesn't escape commas inside quoted fields the same way RFC 4180
 *  does, but the simple case (``"A","B",1``) works — and unquoted
 *  rows with no embedded commas are the common case. */
function parseCsvRow(line: string): string[] {
  const out: string[] = []
  let cur = ''
  let inQuotes = false
  for (let i = 0; i < line.length; i++) {
    const ch = line[i]
    if (ch === '"') {
      inQuotes = !inQuotes
      continue
    }
    if (ch === ',' && !inQuotes) {
      out.push(cur.trim())
      cur = ''
      continue
    }
    cur += ch
  }
  out.push(cur.trim())
  return out
}

const NODE_WIDTH = 18
const COL_GAP = 220
const NODE_GAP_Y = 14
const PIXELS_PER_VALUE = 6
const TITLE_HEIGHT = 0 // sankey diagrams don't use a title in v1

export interface SankeyLayoutOptions {
  originX?: number
  originY?: number
}

/** Lay the parsed diagram out and emit Collab element inputs. */
export function sankeyToElements(
  diagram: SankeyDiagram,
  options: SankeyLayoutOptions = {},
): CreateElementInput[] {
  const ox = options.originX ?? 0
  const oy = options.originY ?? 0
  const out: CreateElementInput[] = []

  if (diagram.nodes.length === 0) return out

  // Group nodes by column for vertical stacking. Sort each column
  // alphabetically so the output is deterministic.
  const byCol = new Map<number, SankeyNode[]>()
  for (const n of diagram.nodes) {
    if (!byCol.has(n.column)) byCol.set(n.column, [])
    byCol.get(n.column)!.push(n)
  }
  for (const arr of byCol.values()) arr.sort((a, b) => a.id.localeCompare(b.id))
  const sortedCols = Array.from(byCol.keys()).sort((a, b) => a - b)

  // Position each node + record its centre/top/bottom for the link
  // geometry.
  const positions = new Map<
    string,
    { x: number; y: number; w: number; h: number }
  >()
  for (const col of sortedCols) {
    const nodes = byCol.get(col)!
    let cursorY = oy + TITLE_HEIGHT
    for (const node of nodes) {
      const h = Math.max(20, node.size * PIXELS_PER_VALUE)
      const x = ox + col * COL_GAP
      positions.set(node.id, { x, y: cursorY, w: NODE_WIDTH, h })
      cursorY += h + NODE_GAP_Y
    }
  }

  // Links — one line per link, stroke width proportional to value.
  // Drawn before nodes so the bars paint over the link ends.
  diagram.links.forEach((l, idx) => {
    const a = positions.get(l.source)
    const b = positions.get(l.target)
    if (!a || !b) return
    const sx = a.x + a.w
    const sy = a.y + a.h / 2
    const tx = b.x
    const ty = b.y + b.h / 2
    const minX = Math.min(sx, tx)
    const minY = Math.min(sy, ty)
    out.push({
      type: 'line',
      x: minX,
      y: minY,
      width: Math.abs(tx - sx),
      height: Math.abs(ty - sy),
      points: [sx - minX, sy - minY, tx - minX, ty - minY],
      strokeColor: '#1971c2',
      fillColor: 'transparent',
      fillStyle: 'none',
      strokeWidth: Math.max(1, Math.min(40, l.value * PIXELS_PER_VALUE)),
      strokeStyle: 'solid',
      roughness: 0,
      opacity: 50,
      seed: hash(`sankey-link-${idx}`),
      version: 0,
      locked: false,
      angle: 0,
      zIndex: 0,
      groupIds: [],
    } as CreateElementInput)
  })

  // Node bars + labels.
  for (const node of diagram.nodes) {
    const pos = positions.get(node.id)
    if (!pos) continue
    out.push({
      type: 'rect',
      x: pos.x,
      y: pos.y,
      width: pos.w,
      height: pos.h,
      strokeColor: '#1e1e1e',
      fillColor: '#1e1e1e',
      fillStyle: 'solid',
      strokeWidth: 1,
      strokeStyle: 'solid',
      roughness: 0,
      opacity: 100,
      seed: hash(`sankey-node-${node.id}`),
      version: 0,
      locked: false,
      angle: 0,
      zIndex: 0,
      groupIds: [],
      roundness: 2,
    } as CreateElementInput)
    // Label sits to the right of the bar (or to the left for the
    // last column so the label doesn't run off into empty space).
    const isLast = node.column === Math.max(...sortedCols)
    out.push({
      type: 'text',
      x: isLast ? pos.x - 130 : pos.x + pos.w + 6,
      y: pos.y + pos.h / 2 - 9,
      width: 124,
      height: 18,
      text: `${node.id} (${node.size})`,
      fontFamily: 'sans',
      fontSize: 12,
      textAlign: isLast ? 'right' : 'left',
      strokeColor: '#1e1e1e',
      fillColor: 'transparent',
      fillStyle: 'none',
      strokeWidth: 1,
      strokeStyle: 'solid',
      roughness: 0,
      opacity: 100,
      seed: hash(`sankey-label-${node.id}`),
      version: 0,
      locked: false,
      angle: 0,
      zIndex: 0,
      groupIds: [],
    } as CreateElementInput)
  }

  return out
}

function hash(s: string): number {
  let h = 5381
  for (let i = 0; i < s.length; i++) h = (h * 33) ^ s.charCodeAt(i)
  return h >>> 0
}
