/**
 * Entity-Relationship subset of Mermaid → Collab elements.
 *
 * Parses the common ER syntax — entities with optional attribute
 * blocks, and the four relationship arrow forms with cardinality
 * markers — and lays it out as a roughly-square grid of boxed
 * entities with labelled lines between them.
 *
 * What we handle
 * --------------
 *   ``erDiagram``                          — header
 *   ``CUSTOMER ||--o{ ORDER : places``     — relationship with label
 *   ``CUSTOMER ||--o{ ORDER``              — relationship without
 *   ``CUSTOMER { string name PK }``        — entity attribute block
 *   ``%% comment`` lines                   — skipped
 *
 * Cardinality markers on each end are parsed and recorded as text
 * (``one``, ``zero or one``, ``one or more``, ``zero or more``) so the
 * line label includes them; we don't render the visual crow's-foot
 * notation in v1 — that's a custom arrow-head per cardinality and
 * each notation needs its own glyph. The text label captures the
 * meaning regardless.
 *
 * Out of scope (decays harmlessly to "ignored line"):
 *   - identifying-vs-non-identifying line styles (``--`` vs ``..``)
 *   - aliases, namespaces
 *   - inline ``"comment"`` strings on attributes
 */

import type { CreateElementInput } from './element-store'

export type Cardinality = 'one' | 'zero or one' | 'one or more' | 'zero or more'

export interface ErAttribute {
  /** Attribute name as it appeared in the source. */
  name: string
  /** Type token (``string``, ``int``, …). */
  type: string
  /** Trailing tokens — typically ``PK``, ``FK``, ``UK``, or empty. */
  tags: string
}

export interface ErEntity {
  id: string
  attributes: ErAttribute[]
}

export interface ErRelationship {
  from: string
  to: string
  fromCardinality: Cardinality
  toCardinality: Cardinality
  /** Optional human label after the ``:``. */
  label: string
  /** ``true`` for ``..`` (non-identifying) — rendered as dashed. */
  dashed: boolean
}

export interface ErDiagram {
  entities: ErEntity[]
  relationships: ErRelationship[]
}

/** Map a 2-character left-side cardinality token to its text form. */
function leftCardinality(token: string): Cardinality | null {
  switch (token) {
    case '||':
      return 'one'
    case '|o':
      return 'zero or one'
    case '}|':
      return 'one or more'
    case '}o':
      return 'zero or more'
    default:
      return null
  }
}

/** Same for the right-side token (mirror image of the left). */
function rightCardinality(token: string): Cardinality | null {
  switch (token) {
    case '||':
      return 'one'
    case 'o|':
      return 'zero or one'
    case '|{':
      return 'one or more'
    case 'o{':
      return 'zero or more'
    default:
      return null
  }
}

/** Parse the ER source. Returns ``null`` when the input doesn't begin
 *  with ``erDiagram`` so the caller can fall through to the generic
 *  "unsupported kind" message. */
export function parseErDiagram(source: string): ErDiagram | null {
  const lines = source.split(/\r?\n/)
  let i = 0
  while (i < lines.length && !lines[i].trim()) i++
  const header = lines[i]?.trim() ?? ''
  if (!/^erDiagram\b/i.test(header)) return null
  i++

  const entities = new Map<string, ErEntity>()
  const relationships: ErRelationship[] = []

  const ensure = (id: string): ErEntity => {
    let e = entities.get(id)
    if (!e) {
      e = { id, attributes: [] }
      entities.set(id, e)
    }
    return e
  }

  let openEntity: ErEntity | null = null

  for (; i < lines.length; i++) {
    const raw = lines[i]
    const line = raw.split('%%')[0].trim()
    if (line.length === 0) continue

    if (openEntity) {
      if (line === '}') {
        openEntity = null
        continue
      }
      // ``type name`` or ``type name PK`` — split on whitespace,
      // first two tokens are type + name (Mermaid ER puts type first),
      // anything after is collected as tags.
      const parts = line.split(/\s+/)
      if (parts.length < 2) continue
      openEntity.attributes.push({
        type: parts[0],
        name: parts[1],
        tags: parts.slice(2).join(' '),
      })
      continue
    }

    // Entity attribute block: ``ENTITY {`` opens, ``}`` closes.
    const blockOpen = /^([A-Z_][\w-]*)\s*\{(.*)$/i.exec(line)
    if (blockOpen) {
      const e = ensure(blockOpen[1])
      openEntity = e
      // Same-line ``ENTITY { string name PK }`` form.
      const inline = blockOpen[2].trim()
      if (inline.endsWith('}')) {
        const body = inline.slice(0, -1).trim()
        if (body.length > 0) {
          const parts = body.split(/\s+/)
          if (parts.length >= 2) {
            e.attributes.push({
              type: parts[0],
              name: parts[1],
              tags: parts.slice(2).join(' '),
            })
          }
        }
        openEntity = null
      }
      continue
    }

    // Relationship: ``A LCARD..RCARD B : label`` or
    // ``A LCARD--RCARD B`` (no label). The middle separator is
    // ``--`` (identifying / solid) or ``..`` (non-identifying /
    // dashed). LCARD ∈ ``||``, ``|o``, ``}|``, ``}o``;
    // RCARD ∈ ``||``, ``o|``, ``|{``, ``o{``.
    // Left-cardinality tokens read pipe-first / brace-first ( ``||``,
    // ``|o``, ``}|``, ``}o`` ). Right-cardinality is the mirror image
    // ( ``||``, ``o|``, ``|{``, ``o{`` ). Keep the alternations
    // disjoint by side so ``A |o--|| B`` parses correctly — getting
    // these reversed quietly drops the "zero or one" cases.
    const relMatch =
      /^([A-Z_][\w-]*)\s+(\|\||\|o|\}\||\}o)(--|\.\.)(\|\||o\||\|\{|o\{)\s+([A-Z_][\w-]*)(?:\s*:\s*(.+))?$/i.exec(
        line,
      )
    if (relMatch) {
      const from = relMatch[1]
      const lcard = relMatch[2]
      const sep = relMatch[3]
      const rcard = relMatch[4]
      const to = relMatch[5]
      const label = relMatch[6]?.trim() ?? ''
      const fromC = leftCardinality(lcard)
      const toC = rightCardinality(rcard)
      if (fromC && toC) {
        ensure(from)
        ensure(to)
        relationships.push({
          from,
          to,
          fromCardinality: fromC,
          toCardinality: toC,
          label,
          dashed: sep === '..',
        })
      }
      continue
    }

    // Standalone entity declaration ``CUSTOMER`` (no body, no
    // relationship) — Mermaid is lenient here, so we accept it.
    if (/^[A-Z_][\w-]*$/i.test(line)) {
      ensure(line)
      continue
    }
  }

  return {
    entities: Array.from(entities.values()),
    relationships,
  }
}

const ENTITY_WIDTH = 180
const ENTITY_HEADER_HEIGHT = 32
const ENTITY_ROW_HEIGHT = 18
const ENTITY_GAP_X = 80
const ENTITY_GAP_Y = 80

export interface ErLayoutOptions {
  originX?: number
  originY?: number
  columns?: number
}

/** Lay out the parsed diagram and emit Collab element inputs. Same
 *  grid pattern as the class-diagram layout — square-ish columns,
 *  per-row height rebaseline so a tall entity doesn't overlap a
 *  short one beside it. */
export function erDiagramToElements(
  diagram: ErDiagram,
  options: ErLayoutOptions = {},
): CreateElementInput[] {
  const ox = options.originX ?? 0
  const oy = options.originY ?? 0
  const cols = Math.max(
    1,
    options.columns ?? Math.ceil(Math.sqrt(diagram.entities.length || 1)),
  )
  const out: CreateElementInput[] = []

  const positions = new Map<
    string,
    { x: number; y: number; w: number; h: number }
  >()
  let rowOffset = 0
  let rowIndex = 0
  let rowMaxHeight = 0
  diagram.entities.forEach((e, idx) => {
    if (idx > 0 && idx % cols === 0) {
      rowOffset += rowMaxHeight + ENTITY_GAP_Y
      rowMaxHeight = 0
      rowIndex = 0
    }
    const x = ox + rowIndex * (ENTITY_WIDTH + ENTITY_GAP_X)
    const y = oy + rowOffset
    const h = entityHeight(e)
    positions.set(e.id, { x, y, w: ENTITY_WIDTH, h })
    rowIndex++
    if (h > rowMaxHeight) rowMaxHeight = h
  })

  for (const e of diagram.entities) {
    const pos = positions.get(e.id)!
    out.push({
      type: 'rect',
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
      seed: hash(e.id),
      version: 0,
      locked: false,
      angle: 0,
      zIndex: 0,
      groupIds: [],
      roundness: 4,
    } as CreateElementInput)
    // Header label (entity name).
    out.push({
      type: 'text',
      x: pos.x + 6,
      y: pos.y + 8,
      width: pos.w - 12,
      height: ENTITY_HEADER_HEIGHT - 16,
      text: e.id,
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
      seed: hash('hdr-' + e.id),
      version: 0,
      locked: false,
      angle: 0,
      zIndex: 0,
      groupIds: [],
    } as CreateElementInput)
    // Divider when there are attributes.
    if (e.attributes.length > 0) {
      const dividerY = pos.y + ENTITY_HEADER_HEIGHT
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
        seed: hash('div-' + e.id),
        version: 0,
        locked: false,
        angle: 0,
        zIndex: 0,
        groupIds: [],
      } as CreateElementInput)
    }
    // Attribute rows — one text element each, monospace so PK / FK
    // tags read like field annotations.
    e.attributes.forEach((attr, ai) => {
      const ry = pos.y + ENTITY_HEADER_HEIGHT + 4 + ai * ENTITY_ROW_HEIGHT
      const display = attr.tags
        ? `${attr.type} ${attr.name}  ${attr.tags}`
        : `${attr.type} ${attr.name}`
      out.push({
        type: 'text',
        x: pos.x + 8,
        y: ry,
        width: pos.w - 16,
        height: ENTITY_ROW_HEIGHT - 2,
        text: display,
        fontFamily: 'mono',
        fontSize: 12,
        textAlign: 'left',
        strokeColor: '#1e1e1e',
        fillColor: 'transparent',
        fillStyle: 'none',
        strokeWidth: 1,
        strokeStyle: 'solid',
        roughness: 0,
        opacity: 100,
        seed: hash(`attr-${e.id}-${ai}`),
        version: 0,
        locked: false,
        angle: 0,
        zIndex: 0,
        groupIds: [],
      } as CreateElementInput)
    })
  }

  // Relationships — line between centres + label text in the middle.
  diagram.relationships.forEach((rel, idx) => {
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
      type: 'line',
      x: minX,
      y: minY,
      width: Math.abs(bx - ax),
      height: Math.abs(by - ay),
      points: [ax - minX, ay - minY, bx - minX, by - minY],
      strokeColor: '#1e1e1e',
      fillColor: 'transparent',
      fillStyle: 'none',
      strokeWidth: 1,
      strokeStyle: rel.dashed ? 'dashed' : 'solid',
      roughness: 0,
      opacity: 100,
      seed: hash(`rel-${idx}`),
      version: 0,
      locked: false,
      angle: 0,
      zIndex: 0,
      groupIds: [],
    } as CreateElementInput)
    // Label combines the verb (rel.label) with cardinalities so the
    // user can read the full relationship sentence even without
    // crow's-foot glyphs: "(one) places (zero or more)".
    const labelText = rel.label
      ? `(${rel.fromCardinality}) ${rel.label} (${rel.toCardinality})`
      : `(${rel.fromCardinality}) → (${rel.toCardinality})`
    const mx = (ax + bx) / 2
    const my = (ay + by) / 2
    out.push({
      type: 'text',
      x: mx - 110,
      y: my - 18,
      width: 220,
      height: 16,
      text: labelText,
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
      seed: hash(`rel-label-${idx}`),
      version: 0,
      locked: false,
      angle: 0,
      zIndex: 0,
      groupIds: [],
    } as CreateElementInput)
  })

  return out
}

function entityHeight(e: ErEntity): number {
  const attrHeight =
    e.attributes.length > 0 ? e.attributes.length * ENTITY_ROW_HEIGHT + 8 : 0
  return ENTITY_HEADER_HEIGHT + attrHeight + 8
}

function hash(s: string): number {
  let h = 5381
  for (let i = 0; i < s.length; i++) h = (h * 33) ^ s.charCodeAt(i)
  return h >>> 0
}
