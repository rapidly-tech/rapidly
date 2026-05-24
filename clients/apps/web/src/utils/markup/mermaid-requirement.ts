/**
 * Requirement-diagram subset of Mermaid → Collab elements.
 *
 * Parses the Mermaid requirementDiagram syntax — requirement and
 * element blocks with attribute lists, plus the seven relationship
 * verbs (contains / copies / derives / satisfies / verifies /
 * refines / traces) — and lays it out as a grid of boxed blocks
 * with labelled lines between them.
 *
 * What we handle
 * --------------
 *   ``requirementDiagram``                    — header
 *   ``requirement test_req { id: 1 ... }``    — requirement block
 *   ``functionalRequirement foo { ... }``     — typed requirement
 *   ``element test_entity { type: ... }``     — element block
 *   ``a - satisfies -> b``                    — relationship
 *   ``%% comment`` lines                      — skipped
 *
 * Out of scope (decays to "ignored line"):
 *   - reverse-arrow forms ``a <- satisfies - b`` (rare)
 *   - validating attribute values against the Mermaid grammar
 *   - rendering distinct line/arrow styles per relationship verb
 *     (every edge in v1 is a plain solid arrow; the verb travels
 *     in the line label so the meaning is preserved)
 */

import type { CreateElementInput } from './element-store'

export type RequirementBlockKind = 'requirement' | 'element'

const REQUIREMENT_KEYWORDS = new Set([
  'requirement',
  'functionalRequirement',
  'interfaceRequirement',
  'performanceRequirement',
  'physicalRequirement',
  'designConstraint',
])

export type RequirementVerb =
  | 'contains'
  | 'copies'
  | 'derives'
  | 'satisfies'
  | 'verifies'
  | 'refines'
  | 'traces'

const VERBS: readonly RequirementVerb[] = [
  'contains',
  'copies',
  'derives',
  'satisfies',
  'verifies',
  'refines',
  'traces',
]

export interface RequirementBlock {
  id: string
  /** ``requirement`` (with all subtypes flattened to this kind) or
   *  ``element``. The original keyword is kept in ``subkind`` so the
   *  renderer can show ``functionalRequirement`` in the header. */
  kind: RequirementBlockKind
  subkind: string
  attributes: Array<{ key: string; value: string }>
}

export interface RequirementRelation {
  from: string
  to: string
  verb: RequirementVerb
}

export interface RequirementDiagram {
  blocks: RequirementBlock[]
  relations: RequirementRelation[]
}

/** Parse the requirement-diagram source. Returns ``null`` when the
 *  input doesn't begin with ``requirementDiagram`` so the caller can
 *  fall through to the generic "unsupported kind" message. */
export function parseRequirementDiagram(
  source: string,
): RequirementDiagram | null {
  const lines = source.split(/\r?\n/)
  let i = 0
  while (i < lines.length && !lines[i].trim()) i++
  const header = lines[i]?.trim() ?? ''
  if (!/^requirementDiagram\b/i.test(header)) return null
  i++

  const blocks = new Map<string, RequirementBlock>()
  const relations: RequirementRelation[] = []

  let openBlock: RequirementBlock | null = null

  for (; i < lines.length; i++) {
    const line = lines[i].split('%%')[0].trim()
    if (line.length === 0) continue

    if (openBlock) {
      if (line === '}') {
        openBlock = null
        continue
      }
      // Attribute line: ``key: value`` (Mermaid is lenient about
      // whitespace and surrounding quotes — strip both).
      const attr = /^(\w+)\s*:\s*(.+?)\s*$/.exec(line)
      if (attr) {
        let value = attr[2]
        if (
          (value.startsWith('"') && value.endsWith('"')) ||
          (value.startsWith("'") && value.endsWith("'"))
        ) {
          value = value.slice(1, -1)
        }
        openBlock.attributes.push({ key: attr[1], value })
      }
      continue
    }

    // Block declaration: ``<keyword> <name> {`` or ``element <name> {``
    const blockOpen = /^(\w+)\s+(\w+)\s*\{(.*)$/.exec(line)
    if (blockOpen) {
      const keyword = blockOpen[1]
      const name = blockOpen[2]
      let kind: RequirementBlockKind | null = null
      if (keyword === 'element') kind = 'element'
      else if (REQUIREMENT_KEYWORDS.has(keyword)) kind = 'requirement'
      if (kind) {
        const block: RequirementBlock = {
          id: name,
          kind,
          subkind: keyword,
          attributes: [],
        }
        blocks.set(name, block)
        // ``key: value }`` on the same opening line happens occasionally.
        const inline = blockOpen[3].trim()
        if (inline.endsWith('}')) {
          const body = inline.slice(0, -1).trim()
          if (body.length > 0) {
            const attr = /^(\w+)\s*:\s*(.+?)\s*$/.exec(body)
            if (attr) block.attributes.push({ key: attr[1], value: attr[2] })
          }
          continue
        }
        if (inline.length > 0) {
          const attr = /^(\w+)\s*:\s*(.+?)\s*$/.exec(inline)
          if (attr) block.attributes.push({ key: attr[1], value: attr[2] })
        }
        openBlock = block
        continue
      }
    }

    // Relationship: ``a - verb -> b`` — the verb sits between two
    // dashes with optional whitespace either side. We accept any
    // recognised verb token; unknown verbs fall through to "ignored".
    const rel = /^(\w+)\s*-\s*(\w+)\s*->\s*(\w+)$/.exec(line)
    if (rel) {
      const from = rel[1]
      const verbToken = rel[2] as RequirementVerb
      const to = rel[3]
      if (VERBS.includes(verbToken)) {
        relations.push({ from, to, verb: verbToken })
      }
      continue
    }

    // Unrecognised line — silently skip.
  }

  return { blocks: Array.from(blocks.values()), relations }
}

const BLOCK_WIDTH = 200
const BLOCK_HEADER_HEIGHT = 36
const BLOCK_ROW_HEIGHT = 16
const BLOCK_GAP_X = 80
const BLOCK_GAP_Y = 80

export interface RequirementLayoutOptions {
  originX?: number
  originY?: number
  columns?: number
}

/** Lay out the parsed diagram and emit Collab element inputs. Same
 *  grid pattern as the class-diagram + ER renderers — square-ish
 *  columns, per-row height rebaseline so a tall block doesn't
 *  overlap a short one beside it. */
export function requirementDiagramToElements(
  diagram: RequirementDiagram,
  options: RequirementLayoutOptions = {},
): CreateElementInput[] {
  const ox = options.originX ?? 0
  const oy = options.originY ?? 0
  const cols = Math.max(
    1,
    options.columns ?? Math.ceil(Math.sqrt(diagram.blocks.length || 1)),
  )
  const out: CreateElementInput[] = []

  const positions = new Map<
    string,
    { x: number; y: number; w: number; h: number }
  >()
  let rowOffset = 0
  let rowIndex = 0
  let rowMaxHeight = 0
  diagram.blocks.forEach((b, idx) => {
    if (idx > 0 && idx % cols === 0) {
      rowOffset += rowMaxHeight + BLOCK_GAP_Y
      rowMaxHeight = 0
      rowIndex = 0
    }
    const x = ox + rowIndex * (BLOCK_WIDTH + BLOCK_GAP_X)
    const y = oy + rowOffset
    const h = blockHeight(b)
    positions.set(b.id, { x, y, w: BLOCK_WIDTH, h })
    rowIndex++
    if (h > rowMaxHeight) rowMaxHeight = h
  })

  for (const block of diagram.blocks) {
    const pos = positions.get(block.id)!
    out.push({
      type: 'rect',
      x: pos.x,
      y: pos.y,
      width: pos.w,
      height: pos.h,
      strokeColor: '#1e1e1e',
      fillColor: block.kind === 'element' ? '#e7f5ff' : '#fff7ed',
      fillStyle: 'solid',
      strokeWidth: 1,
      strokeStyle: 'solid',
      roughness: 0,
      opacity: 100,
      seed: hash('rd-block-' + block.id),
      version: 0,
      locked: false,
      angle: 0,
      zIndex: 0,
      groupIds: [],
      roundness: 4,
    } as CreateElementInput)
    // Header: ``<<subkind>>`` line + name. Two text elements
    // stacked.
    out.push({
      type: 'text',
      x: pos.x + 6,
      y: pos.y + 4,
      width: pos.w - 12,
      height: 14,
      text: `«${block.subkind}»`,
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
      seed: hash('rd-stereo-' + block.id),
      version: 0,
      locked: false,
      angle: 0,
      zIndex: 0,
      groupIds: [],
    } as CreateElementInput)
    out.push({
      type: 'text',
      x: pos.x + 6,
      y: pos.y + 18,
      width: pos.w - 12,
      height: 16,
      text: block.id,
      fontFamily: 'sans',
      fontSize: 14,
      textAlign: 'center',
      fontWeight: 'bold',
      strokeColor: '#1e1e1e',
      fillColor: 'transparent',
      fillStyle: 'none',
      strokeWidth: 1,
      strokeStyle: 'solid',
      roughness: 0,
      opacity: 100,
      seed: hash('rd-name-' + block.id),
      version: 0,
      locked: false,
      angle: 0,
      zIndex: 0,
      groupIds: [],
    } as CreateElementInput)
    // Divider when there are attributes.
    if (block.attributes.length > 0) {
      const dividerY = pos.y + BLOCK_HEADER_HEIGHT
      out.push({
        type: 'line',
        x: pos.x,
        y: dividerY,
        width: pos.w,
        height: 0,
        points: [0, 0, pos.w, 0],
        strokeColor: '#94a3b8',
        fillColor: 'transparent',
        fillStyle: 'none',
        strokeWidth: 1,
        strokeStyle: 'solid',
        roughness: 0,
        opacity: 100,
        seed: hash('rd-div-' + block.id),
        version: 0,
        locked: false,
        angle: 0,
        zIndex: 0,
        groupIds: [],
      } as CreateElementInput)
    }
    // Attribute rows — one text per ``key: value`` pair.
    block.attributes.forEach((attr, ai) => {
      const ry = pos.y + BLOCK_HEADER_HEIGHT + 4 + ai * BLOCK_ROW_HEIGHT
      out.push({
        type: 'text',
        x: pos.x + 8,
        y: ry,
        width: pos.w - 16,
        height: BLOCK_ROW_HEIGHT - 2,
        text: `${attr.key}: ${attr.value}`,
        fontFamily: 'mono',
        fontSize: 11,
        textAlign: 'left',
        strokeColor: '#1e1e1e',
        fillColor: 'transparent',
        fillStyle: 'none',
        strokeWidth: 1,
        strokeStyle: 'solid',
        roughness: 0,
        opacity: 100,
        seed: hash(`rd-attr-${block.id}-${ai}`),
        version: 0,
        locked: false,
        angle: 0,
        zIndex: 0,
        groupIds: [],
      } as CreateElementInput)
    })
  }

  // Relationship arrows + verb labels.
  diagram.relations.forEach((rel, idx) => {
    const a = positions.get(rel.from)
    const b = positions.get(rel.to)
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
      seed: hash(`rd-rel-${idx}`),
      version: 0,
      locked: false,
      angle: 0,
      zIndex: 0,
      groupIds: [],
    } as CreateElementInput)
    // Verb label centred on the arrow.
    const mx = (ax + bx) / 2
    const my = (ay + by) / 2
    out.push({
      type: 'text',
      x: mx - 60,
      y: my - 18,
      width: 120,
      height: 16,
      text: `«${rel.verb}»`,
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
      seed: hash(`rd-rel-label-${idx}`),
      version: 0,
      locked: false,
      angle: 0,
      zIndex: 0,
      groupIds: [],
    } as CreateElementInput)
  })

  return out
}

function blockHeight(b: RequirementBlock): number {
  const attrHeight =
    b.attributes.length > 0 ? b.attributes.length * BLOCK_ROW_HEIGHT + 8 : 0
  return BLOCK_HEADER_HEIGHT + attrHeight + 8
}

function hash(s: string): number {
  let h = 5381
  for (let i = 0; i < s.length; i++) h = (h * 33) ^ s.charCodeAt(i)
  return h >>> 0
}
