/**
 * Class-diagram subset of Mermaid → Collab elements.
 *
 * Parses common UML class-diagram syntax — class declarations with
 * optional bodies of fields + methods, and the standard relationship
 * arrows — and lays it out as a grid of boxed classes with relationship
 * lines between them.
 *
 * What we handle
 * --------------
 *   ``classDiagram``                  — header
 *   ``class Animal``                  — empty class
 *   ``class Animal { ... }``          — class with member body
 *   ``Animal <|-- Dog``               — inheritance (open triangle)
 *   ``Animal --|> Cat``               — inheritance reversed
 *   ``Animal <|.. Dog``               — realization (dashed)
 *   ``Animal --o Dog``                — aggregation (treated as plain
 *                                       arrow — no diamond head in v1)
 *   ``Animal --* Dog``                — composition (same)
 *   ``Animal --> Dog``                — directed association
 *   ``Animal -- Dog``                 — undirected association
 *   ``Animal ..> Dog``                — dependency (dashed arrow)
 *   ``%% comment`` lines              — skipped
 *
 * Inside a class body, lines like ``+name : type`` or ``+do() : void``
 * are captured verbatim (no type inference, no signature parsing —
 * each line becomes one row of text in the rendered class box).
 *
 * Out of scope (decays harmlessly to ignored / approximated):
 *   - ``namespace`` blocks
 *   - ``<<interface>>`` / ``<<abstract>>`` stereotypes
 *   - generic-type ``Class~T~``
 *   - cardinality labels on relationships ``"1" "*"``
 *   - aggregation / composition diamond heads (rendered as plain
 *     arrows for now — the relationship parses and lays out, just
 *     without the distinctive endpoint marker)
 *   - link / annotation lines
 */

import type { CreateElementInput } from './element-store'

export interface ClassDef {
  /** Original identifier from the source. */
  id: string
  /** Display name — same as id unless an alias is later supported. */
  name: string
  /** Each member line is stored as the raw source after the access
   *  modifier was stripped, so the renderer can paint it verbatim. */
  members: string[]
}

export type ClassRelationKind =
  | 'inheritance' // <|-- or --|>
  | 'realization' // <|.. or ..|>
  | 'composition' // --* or *--  (rendered as arrow in v1)
  | 'aggregation' // --o or o--  (rendered as arrow in v1)
  | 'association-directed' // -->
  | 'association' // --
  | 'dependency' // ..>

export interface ClassRelation {
  from: string
  to: string
  kind: ClassRelationKind
  /** ``true`` when the relationship line should be dashed. */
  dashed: boolean
}

export interface ClassDiagram {
  classes: ClassDef[]
  relations: ClassRelation[]
}

/** Parse the class-diagram source. Returns ``null`` when the input
 *  doesn't start with ``classDiagram`` so the caller can fall through
 *  to the generic "unsupported kind" message. */
export function parseClassDiagram(source: string): ClassDiagram | null {
  const lines = source.split(/\r?\n/)
  let i = 0
  while (i < lines.length && !lines[i].trim()) i++
  const header = lines[i]?.trim() ?? ''
  if (!/^classDiagram\b/i.test(header)) return null
  i++

  const classes = new Map<string, ClassDef>()
  const relations: ClassRelation[] = []
  const ensure = (id: string): ClassDef => {
    let c = classes.get(id)
    if (!c) {
      c = { id, name: id, members: [] }
      classes.set(id, c)
    }
    return c
  }

  let openClass: ClassDef | null = null

  for (; i < lines.length; i++) {
    const raw = lines[i]
    const line = raw.split('%%')[0].trim()
    if (line.length === 0) continue

    // Inside a class body: collect member lines until we hit ``}``.
    if (openClass) {
      if (line === '}') {
        openClass = null
        continue
      }
      // Strip leading access modifier (``+`` / ``-`` / ``#`` / ``~``)
      // — we don't render the symbol but want to surface the rest of
      // the line verbatim. Keep blank-after-strip as a row separator.
      const member = line.replace(/^[+\-#~]\s*/, '')
      openClass.members.push(member)
      continue
    }

    // Class declaration — opening brace on the same line, opening
    // brace on the next line, or no body at all.
    const classOpen = /^class\s+(\w+)\s*\{(.*)$/i.exec(line)
    if (classOpen) {
      const c = ensure(classOpen[1])
      openClass = c
      // Same-line members (``class A { +x: int }``): split on the
      // closing brace. Anything after the brace is currently ignored.
      const inline = classOpen[2].trim()
      if (inline.endsWith('}')) {
        const body = inline.slice(0, -1).trim()
        if (body.length > 0) {
          c.members.push(body.replace(/^[+\-#~]\s*/, ''))
        }
        openClass = null
      } else if (inline.length > 0) {
        c.members.push(inline.replace(/^[+\-#~]\s*/, ''))
      }
      continue
    }
    const classNoBody = /^class\s+(\w+)\s*$/i.exec(line)
    if (classNoBody) {
      ensure(classNoBody[1])
      continue
    }
    const classOpenNextLine = /^class\s+(\w+)\s*$/i.exec(line)
    if (classOpenNextLine) {
      ensure(classOpenNextLine[1])
      continue
    }

    // Relationships — match longest forms first so e.g. ``<|--`` isn't
    // mis-parsed as ``<-`` then ``--``. The regex captures from / op /
    // to; the op string drives the kind + dashed mapping.
    const rel = matchRelation(line)
    if (rel) {
      ensure(rel.from)
      ensure(rel.to)
      relations.push(rel)
      continue
    }

    // Unrecognised line — silently skip.
  }

  return { classes: Array.from(classes.values()), relations }
}

/** Tabular operator dispatch — exhaustive over the operators we
 *  support. Returns ``null`` when the line doesn't look like a
 *  relationship at all so the caller can try other line shapes. */
function matchRelation(line: string): ClassRelation | null {
  // Operators ordered longest-first within each shape so a 4-char
  // op doesn't match a 2-char prefix. Accept either side's arrowhead.
  // Operators sorted by length to stop the regex consuming a partial.
  const operators: Array<{
    op: string
    kind: ClassRelationKind
    dashed: boolean
    /** Where the arrow head ends up — ``to`` means head at the right
     *  participant, ``from`` means at the left. ``none`` is
     *  undirected. We don't currently render different head shapes
     *  per kind, but the field is already wired so a future PR can
     *  add diamond / triangle heads without re-walking the parser. */
    head: 'from' | 'to' | 'none'
  }> = [
    { op: '<|--', kind: 'inheritance', dashed: false, head: 'from' },
    { op: '--|>', kind: 'inheritance', dashed: false, head: 'to' },
    { op: '<|..', kind: 'realization', dashed: true, head: 'from' },
    { op: '..|>', kind: 'realization', dashed: true, head: 'to' },
    { op: '*--', kind: 'composition', dashed: false, head: 'from' },
    { op: '--*', kind: 'composition', dashed: false, head: 'to' },
    { op: 'o--', kind: 'aggregation', dashed: false, head: 'from' },
    { op: '--o', kind: 'aggregation', dashed: false, head: 'to' },
    { op: '<--', kind: 'association-directed', dashed: false, head: 'from' },
    { op: '-->', kind: 'association-directed', dashed: false, head: 'to' },
    { op: '<..', kind: 'dependency', dashed: true, head: 'from' },
    { op: '..>', kind: 'dependency', dashed: true, head: 'to' },
    { op: '..', kind: 'association', dashed: true, head: 'none' },
    { op: '--', kind: 'association', dashed: false, head: 'none' },
  ]
  for (const { op, kind, dashed } of operators) {
    // Escape the operator for use in a regex (`.` and `|` are special).
    const escaped = op.replace(/[.|*]/g, (m) => `\\${m}`)
    const re = new RegExp(`^(\\w+)\\s*${escaped}\\s*(\\w+)(?:\\s*:\\s*.+)?$`)
    const m = re.exec(line)
    if (m) {
      return { from: m[1], to: m[2], kind, dashed }
    }
  }
  return null
}

const CLASS_WIDTH = 160
const CLASS_HEADER_HEIGHT = 32
const CLASS_ROW_HEIGHT = 18
const CLASS_GAP_X = 80
const CLASS_GAP_Y = 80

export interface ClassLayoutOptions {
  originX?: number
  originY?: number
  /** Number of class boxes per row. Defaults to ``ceil(sqrt(N))`` —
   *  a roughly square grid that scales sensibly from 1 to dozens of
   *  classes. */
  columns?: number
}

/** Layout: a roughly-square grid of class boxes, with relationship
 *  arrows drawn between the centres of each pair. The user is
 *  expected to tidy up afterwards using the regular select / move
 *  tools — auto-layout is just a starting point. */
export function classDiagramToElements(
  diagram: ClassDiagram,
  options: ClassLayoutOptions = {},
): CreateElementInput[] {
  const ox = options.originX ?? 0
  const oy = options.originY ?? 0
  const cols = Math.max(
    1,
    options.columns ?? Math.ceil(Math.sqrt(diagram.classes.length || 1)),
  )
  const out: CreateElementInput[] = []

  // Compute one bounding box per class so the relationship arrows can
  // anchor on box centres without knowing per-class member counts.
  const positions = new Map<
    string,
    { x: number; y: number; w: number; h: number }
  >()
  // Track row max-height so the next row starts below the tallest
  // class in the previous row.
  let rowOffset = 0
  let rowIndex = 0
  let rowMaxHeight = 0
  diagram.classes.forEach((cls, idx) => {
    if (idx > 0 && idx % cols === 0) {
      rowOffset += rowMaxHeight + CLASS_GAP_Y
      rowMaxHeight = 0
      rowIndex = 0
    }
    const x = ox + rowIndex * (CLASS_WIDTH + CLASS_GAP_X)
    const y = oy + rowOffset
    const h = classBoxHeight(cls)
    positions.set(cls.id, { x, y, w: CLASS_WIDTH, h })
    rowIndex++
    if (h > rowMaxHeight) rowMaxHeight = h
  })

  // Class boxes — one rect per class plus one text element per row
  // (header name + each member line).
  for (const cls of diagram.classes) {
    const pos = positions.get(cls.id)!
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
      seed: hash(cls.id),
      version: 0,
      locked: false,
      angle: 0,
      zIndex: 0,
      groupIds: [],
      roundness: 4,
    } as CreateElementInput)
    // Header label.
    out.push({
      type: 'text',
      x: pos.x + 6,
      y: pos.y + 8,
      width: pos.w - 12,
      height: CLASS_HEADER_HEIGHT - 16,
      text: cls.name,
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
      seed: hash('hdr-' + cls.id),
      version: 0,
      locked: false,
      angle: 0,
      zIndex: 0,
      groupIds: [],
    } as CreateElementInput)
    // Divider line between header and members (only when there are
    // members — an empty class doesn't need the line).
    if (cls.members.length > 0) {
      const dividerY = pos.y + CLASS_HEADER_HEIGHT
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
        seed: hash('div-' + cls.id),
        version: 0,
        locked: false,
        angle: 0,
        zIndex: 0,
        groupIds: [],
      } as CreateElementInput)
    }
    // Member rows — one text element per line. Kept simple: each
    // line is its own absolute-positioned text so wrapping isn't a
    // worry.
    cls.members.forEach((member, mi) => {
      const ry = pos.y + CLASS_HEADER_HEIGHT + 4 + mi * CLASS_ROW_HEIGHT
      out.push({
        type: 'text',
        x: pos.x + 8,
        y: ry,
        width: pos.w - 16,
        height: CLASS_ROW_HEIGHT - 2,
        text: member,
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
        seed: hash(`mem-${cls.id}-${mi}`),
        version: 0,
        locked: false,
        angle: 0,
        zIndex: 0,
        groupIds: [],
      } as CreateElementInput)
    })
  }

  // Relationship arrows. Each emits one arrow element from one box's
  // centre to the other; the existing arrow renderer trims at the
  // bounding box edges so the line doesn't enter the boxes.
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
    const width = Math.abs(bx - ax)
    const height = Math.abs(by - ay)
    out.push({
      type: 'arrow',
      x: minX,
      y: minY,
      width,
      height,
      points: [ax - minX, ay - minY, bx - minX, by - minY],
      startArrowhead: null,
      endArrowhead: rel.kind === 'association' ? null : 'triangle',
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
  })

  return out
}

function classBoxHeight(cls: ClassDef): number {
  // Header + (members? divider gap : 0) + per-member row + small
  // bottom padding so the last member doesn't kiss the box edge.
  const memberHeight =
    cls.members.length > 0 ? cls.members.length * CLASS_ROW_HEIGHT + 8 : 0
  return CLASS_HEADER_HEIGHT + memberHeight + 8
}

/** djb2-like seed for the rough renderer's per-shape randomness. */
function hash(s: string): number {
  let h = 5381
  for (let i = 0; i < s.length; i++) h = (h * 33) ^ s.charCodeAt(i)
  return h >>> 0
}
