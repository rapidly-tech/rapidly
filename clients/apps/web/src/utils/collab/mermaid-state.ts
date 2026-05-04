/**
 * State-diagram subset of Mermaid → Collab elements.
 *
 * Parses the common state-diagram syntax — states (declared inline
 * or via ``state X``), the ``[*]`` start/end pseudo-state, and
 * transitions with optional labels — and lays it out using a
 * longest-path layering scheme (same idea the flowchart layout uses)
 * so the diagram reads top-to-bottom by default.
 *
 * What we handle
 * --------------
 *   ``stateDiagram`` / ``stateDiagram-v2``  — header
 *   ``state SomeState``                     — declaration
 *   ``state SomeState as Friendly Name``    — alias
 *   ``A --> B``                             — transition
 *   ``A --> B : label``                     — transition with label
 *   ``[*] --> A``                           — entry transition
 *   ``A --> [*]``                           — exit transition
 *   ``%% comment`` lines                    — skipped
 *
 * Out of scope (decays to "ignored line" so a single unfamiliar
 * keyword doesn't abort the whole parse):
 *   - nested ``state X { ... }`` blocks (flattened — child states
 *     parse, but their parent containment is dropped in v1)
 *   - choice / fork / join pseudo-states
 *   - concurrent regions (``--`` separator inside a state body)
 *   - notes
 *   - direction LR / TB pragmas (always laid out top-down)
 */

import type { CreateElementInput } from './element-store'

/** ``[*]`` is treated as a single virtual node id. The renderer
 *  paints it as a small filled circle so the user reads it as the
 *  start / end pseudo-state. */
const TERMINAL = '[*]'

export interface StateNode {
  id: string
  label: string
  /** ``true`` for ``[*]`` — the renderer paints it as a circle. */
  terminal: boolean
}

export interface StateTransition {
  from: string
  to: string
  label: string
}

export interface StateDiagram {
  nodes: Map<string, StateNode>
  transitions: StateTransition[]
}

/** Parse the state-diagram source. Returns ``null`` when the input
 *  doesn't begin with ``stateDiagram`` (or ``stateDiagram-v2``) so
 *  the caller can fall through to the generic "unsupported kind"
 *  message. */
export function parseStateDiagram(source: string): StateDiagram | null {
  const lines = source.split(/\r?\n/)
  let i = 0
  while (i < lines.length && !lines[i].trim()) i++
  const header = lines[i]?.trim() ?? ''
  if (!/^stateDiagram(?:-v2)?\b/i.test(header)) return null
  i++

  const nodes = new Map<string, StateNode>()
  const transitions: StateTransition[] = []

  const ensure = (id: string, label?: string): StateNode => {
    let n = nodes.get(id)
    if (!n) {
      n = {
        id,
        label: label ?? (id === TERMINAL ? '' : id),
        terminal: id === TERMINAL,
      }
      nodes.set(id, n)
    } else if (label && !n.terminal) {
      n.label = label
    }
    return n
  }

  // Always seed the terminal so a diagram that only references it
  // implicitly via a transition still records its existence.
  // (``ensure`` is called per transition anyway, so this is mostly
  // a clarity comment — no preallocation needed.)

  for (; i < lines.length; i++) {
    const line = lines[i].split('%%')[0].trim()
    if (line.length === 0) continue
    if (line === '}') continue // close of a (flattened) state block

    // ``state Name`` or ``state Name as Friendly Name``
    const stateAlias = /^state\s+(\w+)\s+as\s+(.+?)\s*\{?\s*$/i.exec(line)
    if (stateAlias) {
      ensure(stateAlias[1], stateAlias[2].trim())
      continue
    }
    const stateDecl = /^state\s+(\w+)\s*\{?\s*$/i.exec(line)
    if (stateDecl) {
      ensure(stateDecl[1])
      continue
    }
    // ``state "Display name" as Id`` form (Mermaid alt syntax). The
    // quoted label is the display name; the trailing ``as Id`` is
    // the canonical id used by transitions.
    const stateQuoted = /^state\s+"([^"]+)"\s+as\s+(\w+)\s*\{?\s*$/i.exec(line)
    if (stateQuoted) {
      ensure(stateQuoted[2], stateQuoted[1])
      continue
    }

    // Transition: ``A --> B`` or ``A --> B : label``. Either side
    // may be ``[*]`` (the terminal). The id pattern accepts ``\w+``
    // *or* the literal ``[*]`` token.
    const ID = String.raw`(\w+|\[\*\])`
    const tx = new RegExp(`^${ID}\\s*-->\\s*${ID}\\s*(?::\\s*(.+))?$`).exec(
      line,
    )
    if (tx) {
      const from = tx[1]
      const to = tx[2]
      const label = tx[3]?.trim() ?? ''
      ensure(from)
      ensure(to)
      transitions.push({ from, to, label })
      continue
    }

    // Unrecognised line — silently skip.
  }

  return { nodes, transitions }
}

const STATE_WIDTH = 140
const STATE_HEIGHT = 50
const TERMINAL_RADIUS = 10
const LAYER_GAP_X = 60
const LAYER_GAP_Y = 80

export interface StateLayoutOptions {
  originX?: number
  originY?: number
}

/** Lay out the parsed state diagram and emit Collab element inputs.
 *  Uses a longest-path layering: for each node, its layer is one
 *  more than the maximum layer of its predecessors; nodes with no
 *  predecessors land at layer 0. Within a layer, nodes spread
 *  horizontally with a constant gap.
 *
 *  Cycles are tolerated: ``computeLayers`` short-circuits at a
 *  bounded recursion depth so a self-loop or back-edge doesn't
 *  spin forever.
 */
export function stateDiagramToElements(
  diagram: StateDiagram,
  options: StateLayoutOptions = {},
): CreateElementInput[] {
  const ox = options.originX ?? 0
  const oy = options.originY ?? 0
  const out: CreateElementInput[] = []

  const layers = computeLayers(diagram)
  // Group nodes by layer for horizontal spreading.
  const byLayer = new Map<number, string[]>()
  for (const [id, layer] of layers.entries()) {
    if (!byLayer.has(layer)) byLayer.set(layer, [])
    byLayer.get(layer)!.push(id)
  }
  // Sort each layer alphabetically so the output is deterministic.
  for (const ids of byLayer.values()) ids.sort()

  // Position each node.
  const positions = new Map<
    string,
    { cx: number; cy: number; w: number; h: number }
  >()
  const sortedLayers = Array.from(byLayer.keys()).sort((a, b) => a - b)
  for (const layer of sortedLayers) {
    const ids = byLayer.get(layer)!
    ids.forEach((id, idx) => {
      const node = diagram.nodes.get(id)!
      const isTerminal = node.terminal
      const w = isTerminal ? TERMINAL_RADIUS * 2 : STATE_WIDTH
      const h = isTerminal ? TERMINAL_RADIUS * 2 : STATE_HEIGHT
      const cx = ox + idx * (STATE_WIDTH + LAYER_GAP_X) + STATE_WIDTH / 2
      const cy = oy + layer * (STATE_HEIGHT + LAYER_GAP_Y) + STATE_HEIGHT / 2
      positions.set(id, { cx, cy, w, h })
    })
  }

  // Emit elements.
  for (const node of diagram.nodes.values()) {
    const pos = positions.get(node.id)!
    if (node.terminal) {
      out.push({
        type: 'ellipse',
        x: pos.cx - TERMINAL_RADIUS,
        y: pos.cy - TERMINAL_RADIUS,
        width: TERMINAL_RADIUS * 2,
        height: TERMINAL_RADIUS * 2,
        strokeColor: '#1e1e1e',
        fillColor: '#1e1e1e',
        fillStyle: 'solid',
        strokeWidth: 1,
        strokeStyle: 'solid',
        roughness: 0,
        opacity: 100,
        seed: hash(node.id),
        version: 0,
        locked: false,
        angle: 0,
        zIndex: 0,
        groupIds: [],
      } as CreateElementInput)
      continue
    }
    out.push({
      type: 'rect',
      x: pos.cx - STATE_WIDTH / 2,
      y: pos.cy - STATE_HEIGHT / 2,
      width: STATE_WIDTH,
      height: STATE_HEIGHT,
      strokeColor: '#1e1e1e',
      fillColor: '#f8fafc',
      fillStyle: 'solid',
      strokeWidth: 1,
      strokeStyle: 'solid',
      roughness: 0,
      opacity: 100,
      seed: hash(node.id),
      version: 0,
      locked: false,
      angle: 0,
      zIndex: 0,
      groupIds: [],
      roundness: 16, // states are rendered as rounded rects
    } as CreateElementInput)
    // Label text centred in the rect.
    out.push({
      type: 'text',
      x: pos.cx - STATE_WIDTH / 2 + 6,
      y: pos.cy - 9,
      width: STATE_WIDTH - 12,
      height: 18,
      text: node.label,
      fontFamily: 'sans',
      fontSize: 14,
      textAlign: 'center',
      strokeColor: '#1e1e1e',
      fillColor: 'transparent',
      fillStyle: 'none',
      strokeWidth: 1,
      strokeStyle: 'solid',
      roughness: 0,
      opacity: 100,
      seed: hash('label-' + node.id),
      version: 0,
      locked: false,
      angle: 0,
      zIndex: 0,
      groupIds: [],
    } as CreateElementInput)
  }

  // Transitions.
  diagram.transitions.forEach((tx, idx) => {
    const a = positions.get(tx.from)
    const b = positions.get(tx.to)
    if (!a || !b) return
    const minX = Math.min(a.cx, b.cx)
    const minY = Math.min(a.cy, b.cy)
    const width = Math.abs(b.cx - a.cx)
    const height = Math.abs(b.cy - a.cy)
    out.push({
      type: 'arrow',
      x: minX,
      y: minY,
      width,
      height,
      points: [a.cx - minX, a.cy - minY, b.cx - minX, b.cy - minY],
      startArrowhead: null,
      endArrowhead: 'triangle',
      strokeColor: '#1e1e1e',
      fillColor: 'transparent',
      fillStyle: 'none',
      strokeWidth: 1,
      strokeStyle: 'solid',
      roughness: 0,
      opacity: 100,
      seed: hash(`tx-${idx}`),
      version: 0,
      locked: false,
      angle: 0,
      zIndex: 0,
      groupIds: [],
    } as CreateElementInput)
    if (tx.label.length > 0) {
      // Label sits at the midpoint of the arrow with a small upward
      // offset so it doesn't overlap the line.
      const mx = (a.cx + b.cx) / 2
      const my = (a.cy + b.cy) / 2
      out.push({
        type: 'text',
        x: mx - 80,
        y: my - 18,
        width: 160,
        height: 16,
        text: tx.label,
        fontFamily: 'sans',
        fontSize: 12,
        textAlign: 'center',
        strokeColor: '#475569',
        fillColor: 'transparent',
        fillStyle: 'none',
        strokeWidth: 1,
        strokeStyle: 'solid',
        roughness: 0,
        opacity: 100,
        seed: hash(`tx-label-${idx}`),
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

/** Compute the layer of every node via a longest-path walk. Cycles
 *  short-circuit at a depth ceiling so a self-loop or back-edge
 *  doesn't spin forever. */
export function computeLayers(diagram: StateDiagram): Map<string, number> {
  const layers = new Map<string, number>()
  // Cap at the node count: longest acyclic path can't exceed that.
  const maxDepth = diagram.nodes.size
  // Predecessor map for the longest-path lookup.
  const preds = new Map<string, string[]>()
  for (const id of diagram.nodes.keys()) preds.set(id, [])
  for (const tx of diagram.transitions) {
    preds.get(tx.to)?.push(tx.from)
  }
  const visiting = new Set<string>()
  const layerOf = (id: string, depth: number): number => {
    if (depth > maxDepth) return 0
    const cached = layers.get(id)
    if (cached !== undefined) return cached
    if (visiting.has(id)) return 0 // cycle: fall back to layer 0
    visiting.add(id)
    const ps = preds.get(id) ?? []
    let max = -1
    for (const p of ps) {
      const pl = layerOf(p, depth + 1)
      if (pl > max) max = pl
    }
    visiting.delete(id)
    const layer = max + 1
    layers.set(id, layer)
    return layer
  }
  for (const id of diagram.nodes.keys()) layerOf(id, 0)
  return layers
}

/** djb2-like seed for the rough renderer's per-shape randomness. */
function hash(s: string): number {
  let h = 5381
  for (let i = 0; i < s.length; i++) h = (h * 33) ^ s.charCodeAt(i)
  return h >>> 0
}
