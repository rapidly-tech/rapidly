/**
 * Block-diagram subset of Mermaid → Collab elements.
 *
 * Parses the ``block-beta`` syntax — ``columns N`` directive,
 * block-per-line layout with optional column-spanning ``id:N``
 * modifiers, optional shape wrappers around labels, and arrow
 * connectors — and lays it out as a grid of styled cells.
 *
 * What we handle
 * --------------
 *   ``block-beta``                       — header (alias: ``block``)
 *   ``columns 3``                        — set the grid width
 *   ``a b c``                            — three blocks across one row
 *   ``a:2 b``                            — block ``a`` spans 2 columns
 *   ``A["Label"]``                       — rect shape with label
 *   ``B(("Cloud"))``                     — circle shape with label
 *   ``C("Rounded")``                     — rounded shape
 *   ``A --> B``                          — arrow between blocks
 *   ``A -- "label" --> B``               — arrow with edge label
 *   ``%% comment`` lines                 — skipped
 *
 * Out of scope (decays to "ignored line"):
 *   - nested ``block ... end`` groups (flattened)
 *   - ``space`` placeholder cells
 *   - ``classDef`` styling
 *   - ``columns auto``
 */

import type { CreateElementInput } from './element-store'

export type BlockShape = 'rect' | 'rounded' | 'circle' | 'default'

export interface BlockNode {
  id: string
  label: string
  shape: BlockShape
  /** How many columns this block spans (default 1). */
  span: number
  /** Layout coordinates assigned in the second pass. */
  row: number
  col: number
}

export interface BlockEdge {
  from: string
  to: string
  label: string
}

export interface BlockDiagram {
  columns: number
  blocks: BlockNode[]
  edges: BlockEdge[]
}

/** Parse the block-diagram source. Returns ``null`` when the input
 *  doesn't begin with ``block-beta`` (or ``block``) so the caller can
 *  fall through to the generic "unsupported kind" message. */
export function parseBlockDiagram(source: string): BlockDiagram | null {
  const lines = source.split(/\r?\n/)
  let i = 0
  while (i < lines.length && !lines[i].trim()) i++
  const header = lines[i]?.trim() ?? ''
  if (!/^block(?:-beta)?\b/i.test(header)) return null
  i++

  let columns = 1
  const blocks: BlockNode[] = []
  const blockById = new Map<string, BlockNode>()
  const edges: BlockEdge[] = []

  // We collect block "declarations" first (each row appended to a
  // pending list), then assign row/col positions in a second pass
  // once we know the column count.
  const rows: BlockNode[][] = []

  for (; i < lines.length; i++) {
    const line = lines[i].split('%%')[0].trim()
    if (line.length === 0) continue
    if (line === 'end') continue // close of a (flattened) group block

    // ``columns N`` directive.
    const colsMatch = /^columns\s+(\d+)$/i.exec(line)
    if (colsMatch) {
      columns = Math.max(1, Number(colsMatch[1]))
      continue
    }
    // ``block: foo`` or ``block foo`` — grouping start; we flatten
    // children into the same flow.
    if (/^block\b/i.test(line)) continue

    // Edges first — Mermaid block edges look like ``A --> B`` or
    // ``A -- "label" --> B``. Match before the block-tokeniser since
    // those tokens look like ``A --> B`` if the row only contains
    // a single edge.
    const edgeLabel = /^(\w+)\s*--\s*"([^"]*)"\s*-->\s*(\w+)$/.exec(line)
    if (edgeLabel) {
      edges.push({ from: edgeLabel[1], to: edgeLabel[3], label: edgeLabel[2] })
      continue
    }
    const edge = /^(\w+)\s*-->\s*(\w+)$/.exec(line)
    if (edge) {
      edges.push({ from: edge[1], to: edge[2], label: '' })
      continue
    }

    // Otherwise treat as a row of block tokens. Each token can be:
    //   ``id``                — bare reference / declaration
    //   ``id:N``              — span N columns
    //   ``id["Label"]``       — rect shape
    //   ``id(("Cloud"))``     — circle shape
    //   ``id("Rounded")``     — rounded shape
    //   ``id:N["Label"]``     — span + shape combined
    const rowTokens: BlockNode[] = []
    for (const token of tokeniseRow(line)) {
      const node = parseToken(token)
      if (!node) continue
      const existing = blockById.get(node.id)
      if (existing) {
        // Merge: a later row may upgrade a bare reference with a
        // shape/label, or vice versa.
        if (node.shape !== 'default') existing.shape = node.shape
        if (node.label && existing.label === existing.id) {
          existing.label = node.label
        }
        rowTokens.push(existing)
      } else {
        blockById.set(node.id, node)
        blocks.push(node)
        rowTokens.push(node)
      }
    }
    if (rowTokens.length > 0) rows.push(rowTokens)
  }

  // Second pass: assign row/col positions honouring the ``columns``
  // limit + per-block ``span`` modifiers. Each declared row maps to
  // one or more layout rows depending on how many cells it
  // consumes.
  let layoutRow = 0
  for (const row of rows) {
    let col = 0
    for (const node of row) {
      if (col + node.span > columns) {
        layoutRow++
        col = 0
      }
      node.row = layoutRow
      node.col = col
      col += node.span
    }
    layoutRow++
  }

  return { columns, blocks, edges }
}

/** Split a row of block tokens, respecting bracket / quote nesting so
 *  ``a["x y"] b`` doesn't fragment on the embedded space. */
function tokeniseRow(line: string): string[] {
  const out: string[] = []
  let cur = ''
  let depth = 0
  let inQuotes = false
  for (let i = 0; i < line.length; i++) {
    const ch = line[i]
    if (ch === '"') {
      inQuotes = !inQuotes
      cur += ch
      continue
    }
    if (!inQuotes) {
      if (ch === '[' || ch === '(' || ch === '{') depth++
      else if (ch === ']' || ch === ')' || ch === '}')
        depth = Math.max(0, depth - 1)
      if (ch === ' ' && depth === 0) {
        if (cur.length > 0) out.push(cur)
        cur = ''
        continue
      }
    }
    cur += ch
  }
  if (cur.length > 0) out.push(cur)
  return out
}

/** Parse a single block token into a node descriptor. Returns
 *  ``null`` for unrecognisable input rather than throwing. */
function parseToken(raw: string): BlockNode | null {
  // Strip optional ``:N`` span suffix from the identifier portion
  // (must come before any shape brackets).
  const spanIdMatch = /^(\w+)(?::(\d+))?(.*)$/.exec(raw)
  if (!spanIdMatch) return null
  const id = spanIdMatch[1]
  const span = spanIdMatch[2] ? Math.max(1, Number(spanIdMatch[2])) : 1
  const rest = spanIdMatch[3]

  // Shape wrapper detection — longest first so ``((x))`` doesn't get
  // caught as ``(x)``.
  const cloud = /^\(\(\s*"?([^")]+)"?\s*\)\)$/.exec(rest)
  if (cloud) return blockNode(id, cloud[1].trim(), 'circle', span)
  const rect = /^\[\s*"?([^"\]]+)"?\s*\]$/.exec(rest)
  if (rect) return blockNode(id, rect[1].trim(), 'rect', span)
  const rounded = /^\(\s*"?([^")]+)"?\s*\)$/.exec(rest)
  if (rounded) return blockNode(id, rounded[1].trim(), 'rounded', span)
  if (rest.trim() === '') return blockNode(id, id, 'default', span)
  return null
}

function blockNode(
  id: string,
  label: string,
  shape: BlockShape,
  span: number,
): BlockNode {
  return { id, label, shape, span, row: 0, col: 0 }
}

const CELL_WIDTH = 140
const CELL_HEIGHT = 60
const CELL_GAP_X = 12
const CELL_GAP_Y = 12

export interface BlockLayoutOptions {
  originX?: number
  originY?: number
}

/** Lay the parsed diagram out and emit Collab element inputs. */
export function blockDiagramToElements(
  diagram: BlockDiagram,
  options: BlockLayoutOptions = {},
): CreateElementInput[] {
  const ox = options.originX ?? 0
  const oy = options.originY ?? 0
  const out: CreateElementInput[] = []

  const positionOf = new Map<
    string,
    { x: number; y: number; w: number; h: number }
  >()
  for (const node of diagram.blocks) {
    const w = CELL_WIDTH * node.span + CELL_GAP_X * (node.span - 1)
    const h = CELL_HEIGHT
    const x = ox + node.col * (CELL_WIDTH + CELL_GAP_X)
    const y = oy + node.row * (CELL_HEIGHT + CELL_GAP_Y)
    positionOf.set(node.id, { x, y, w, h })
  }

  // Block cells.
  for (const node of diagram.blocks) {
    const pos = positionOf.get(node.id)!
    if (node.shape === 'circle') {
      out.push({
        type: 'ellipse',
        x: pos.x,
        y: pos.y,
        width: pos.w,
        height: pos.h,
        strokeColor: '#1e1e1e',
        fillColor: '#fff7ed',
        fillStyle: 'solid',
        strokeWidth: 1,
        strokeStyle: 'solid',
        roughness: 0,
        opacity: 100,
        seed: hash(`block-${node.id}`),
        version: 0,
        locked: false,
        angle: 0,
        zIndex: 0,
        groupIds: [],
      } as CreateElementInput)
    } else {
      out.push({
        type: 'rect',
        x: pos.x,
        y: pos.y,
        width: pos.w,
        height: pos.h,
        strokeColor: '#1e1e1e',
        fillColor: '#f8fafc',
        fillStyle: 'solid',
        strokeWidth: 1,
        strokeStyle: 'solid',
        roughness: 0,
        opacity: 100,
        seed: hash(`block-${node.id}`),
        version: 0,
        locked: false,
        angle: 0,
        zIndex: 0,
        groupIds: [],
        roundness: node.shape === 'rounded' ? 14 : 4,
      } as CreateElementInput)
    }
    // Label.
    out.push({
      type: 'text',
      x: pos.x + 6,
      y: pos.y + (CELL_HEIGHT - 18) / 2,
      width: pos.w - 12,
      height: 18,
      text: node.label,
      fontFamily: 'sans',
      fontSize: 13,
      textAlign: 'center',
      strokeColor: '#1e1e1e',
      fillColor: 'transparent',
      fillStyle: 'none',
      strokeWidth: 1,
      strokeStyle: 'solid',
      roughness: 0,
      opacity: 100,
      seed: hash(`block-label-${node.id}`),
      version: 0,
      locked: false,
      angle: 0,
      zIndex: 0,
      groupIds: [],
    } as CreateElementInput)
  }

  // Edges — arrow from one block centre to another.
  diagram.edges.forEach((edge, idx) => {
    const a = positionOf.get(edge.from)
    const b = positionOf.get(edge.to)
    if (!a || !b) return
    const ax = a.x + a.w / 2
    const ay = a.y + a.h / 2
    const bx = b.x + b.w / 2
    const by = b.y + b.h / 2
    const minX = Math.min(ax, bx)
    const minY = Math.min(ay, by)
    out.push({
      type: 'arrow',
      x: minX,
      y: minY,
      width: Math.abs(bx - ax),
      height: Math.abs(by - ay),
      points: [ax - minX, ay - minY, bx - minX, by - minY],
      startArrowhead: null,
      endArrowhead: 'triangle',
      strokeColor: '#1e1e1e',
      fillColor: 'transparent',
      fillStyle: 'none',
      strokeWidth: 1,
      strokeStyle: 'solid',
      roughness: 0,
      opacity: 100,
      seed: hash(`block-edge-${idx}`),
      version: 0,
      locked: false,
      angle: 0,
      zIndex: 0,
      groupIds: [],
    } as CreateElementInput)
    if (edge.label) {
      const mx = (ax + bx) / 2
      const my = (ay + by) / 2
      out.push({
        type: 'text',
        x: mx - 60,
        y: my - 18,
        width: 120,
        height: 14,
        text: edge.label,
        fontFamily: 'sans',
        fontSize: 11,
        textAlign: 'center',
        strokeColor: '#475569',
        fillColor: 'transparent',
        fillStyle: 'none',
        strokeWidth: 1,
        strokeStyle: 'solid',
        roughness: 0,
        opacity: 100,
        seed: hash(`block-edge-label-${idx}`),
        version: 0,
        locked: false,
        angle: 0,
        zIndex: 0,
        groupIds: [],
      } as CreateElementInput)
    }
  })

  return out
}

function hash(s: string): number {
  let h = 5381
  for (let i = 0; i < s.length; i++) h = (h * 33) ^ s.charCodeAt(i)
  return h >>> 0
}
