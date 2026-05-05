/**
 * ZenUML-diagram subset of Mermaid → Collab elements.
 *
 * ZenUML is an alternative sequence-diagram DSL. We render a
 * lifeline-style layout — one column per participant, messages as
 * arrows between columns, ordered top-to-bottom by source order.
 *
 * What we handle
 * --------------
 *   ``zenuml``                        — header
 *   ``title Order flow``              — title
 *   ``@Actor Alice``                  — typed participant declaration
 *   ``@Database DB``                  — (alias: ``@Boundary``,
 *                                       ``@Control``, ``@Entity``)
 *   ``Alice->Bob.placeOrder()``       — sync message (arrow with the
 *                                       method as the label)
 *   ``Alice->>Bob.notify()``          — async message (dashed arrow)
 *   ``Bob->DB.query() { ... }``       — block body's interior is
 *                                       parsed for nested messages
 *   ``return result``                 — return-arrow message
 *   ``if (cond) { ... }``             — body parsed for messages,
 *                                       fragment frame skipped
 *   ``%% comment`` lines              — skipped
 *
 * Out of scope (decays to "ignored line"):
 *   - explicit fragment frames (alt / par / loop boxes)
 *   - assigned return values (``x = Bob.method()``)
 *   - participant styling
 */

import type { CreateElementInput } from './element-store'

export type ZenParticipantKind =
  | 'Actor'
  | 'Boundary'
  | 'Control'
  | 'Entity'
  | 'Database'
  | 'Object'

export interface ZenParticipant {
  id: string
  kind: ZenParticipantKind
}

export interface ZenMessage {
  from: string
  to: string
  label: string
  /** Dashed arrow for async or return messages. */
  dashed: boolean
  /** Return arrows render with an open arrowhead and right-to-left
   *  visual cue (we keep direction, just signal it). */
  isReturn: boolean
}

export interface ZenDiagram {
  title: string
  participants: ZenParticipant[]
  messages: ZenMessage[]
}

const PARTICIPANT_KEYWORDS: Record<string, ZenParticipantKind> = {
  '@Actor': 'Actor',
  '@Boundary': 'Boundary',
  '@Control': 'Control',
  '@Entity': 'Entity',
  '@Database': 'Database',
}

/** Parse the ZenUML source. Returns ``null`` when the input doesn't
 *  start with ``zenuml`` so the caller can fall through to the
 *  generic "unsupported kind" message. */
export function parseZenUml(source: string): ZenDiagram | null {
  const lines = source.split(/\r?\n/)
  let i = 0
  while (i < lines.length && !lines[i].trim()) i++
  const header = lines[i]?.trim() ?? ''
  if (!/^zenuml\b/i.test(header)) return null
  i++

  let title = ''
  const participants = new Map<string, ZenParticipant>()
  const messages: ZenMessage[] = []
  /** Stack of senders implied by ``X->Y { ... }`` blocks. The
   *  innermost sender is the one a bare ``Z.method()`` line targets,
   *  and ``return`` arrows go back to the caller. */
  const callStack: Array<{ from: string; to: string }> = []

  const ensureParticipant = (id: string, kind?: ZenParticipantKind) => {
    if (!id) return
    if (!participants.has(id)) {
      participants.set(id, { id, kind: kind ?? 'Object' })
    } else if (kind) {
      participants.get(id)!.kind = kind
    }
  }

  for (; i < lines.length; i++) {
    const raw = lines[i].split('//')[0].split('%%')[0]
    const line = raw.trim()
    if (line.length === 0) continue

    // Closing brace pops a call frame.
    if (line === '}') {
      callStack.pop()
      continue
    }

    const titleMatch = /^title\s+(.+)$/i.exec(line)
    if (titleMatch) {
      title = titleMatch[1].trim()
      continue
    }

    // Participant declaration: ``@Actor Alice`` etc.
    const partMatch = /^(@\w+)\s+(\w+)\s*$/.exec(line)
    if (partMatch && PARTICIPANT_KEYWORDS[partMatch[1]]) {
      ensureParticipant(partMatch[2], PARTICIPANT_KEYWORDS[partMatch[1]])
      continue
    }

    // Return arrow: ``return value`` — pops back to the caller of
    // the current frame, with the value as the message label.
    const returnMatch = /^return\b\s*(.*)$/i.exec(line)
    if (returnMatch && callStack.length > 0) {
      const top = callStack[callStack.length - 1]
      messages.push({
        from: top.to,
        to: top.from,
        label: returnMatch[1].trim(),
        dashed: true,
        isReturn: true,
      })
      continue
    }

    // Control-flow fragment: ``if (...)``, ``while (...)``, ``for
    // (...)``, ``alt``, ``opt``, ``loop`` — the body is parsed for
    // messages but the fragment frame itself is dropped (no box is
    // rendered). We push a sentinel onto the stack so the matching
    // ``}`` doesn't pop a real call frame.
    const fragMatch = /^(if|while|for|alt|opt|loop|par)\b.*\{?\s*$/i.exec(line)
    if (fragMatch) {
      // Use the current top sender for any nested bare calls.
      const top = callStack[callStack.length - 1]
      callStack.push({ from: top?.from ?? '', to: top?.to ?? '' })
      continue
    }

    // Message: ``A->B.method()`` or ``A->>B.method()`` or ``A.do()``
    // (implicit sender = top of call stack).
    const msgMatch =
      /^(?:(\w+)\s*(->>?|->)\s*)?(\w+)\s*\.\s*(\w+\([^)]*\))\s*\{?\s*$/.exec(
        line,
      )
    if (msgMatch) {
      const explicitFrom = msgMatch[1]
      const op = msgMatch[2]
      const to = msgMatch[3]
      const label = msgMatch[4]
      const from = explicitFrom ?? callStack[callStack.length - 1]?.to ?? ''
      if (!from || !to) continue
      ensureParticipant(from)
      ensureParticipant(to)
      messages.push({
        from,
        to,
        label,
        dashed: op === '->>',
        isReturn: false,
      })
      // If the line ends with `{`, push a frame so nested calls
      // resolve to this one.
      if (line.endsWith('{')) {
        callStack.push({ from, to })
      }
      continue
    }
    // Unrecognised — silently skip.
  }

  return {
    title,
    participants: Array.from(participants.values()),
    messages,
  }
}

const COL_W = 140
const COL_GAP = 60
const HEAD_H = 40
const ROW_H = 36
const TITLE_HEIGHT = 28
const TOP_PAD = 12

export interface ZenLayoutOptions {
  originX?: number
  originY?: number
}

/** Lay out the parsed diagram and emit Collab element inputs. Each
 *  participant becomes a header rect + a vertical lifeline; each
 *  message becomes a horizontal arrow between two lifelines. */
export function zenUmlToElements(
  diagram: ZenDiagram,
  options: ZenLayoutOptions = {},
): CreateElementInput[] {
  const ox = options.originX ?? 0
  const oy = options.originY ?? 0
  const out: CreateElementInput[] = []

  if (diagram.participants.length === 0) {
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

  // Column x for each participant id.
  const cols = new Map<string, number>()
  diagram.participants.forEach((p, idx) => {
    const cx = ox + idx * (COL_W + COL_GAP) + COL_W / 2
    cols.set(p.id, cx)
  })

  // Total lifeline length: header + one row per message + bottom pad.
  const lifelineBottom =
    cursorY + HEAD_H + diagram.messages.length * ROW_H + TOP_PAD * 2

  // Headers + lifelines.
  diagram.participants.forEach((p) => {
    const cx = cols.get(p.id)!
    const fill = pickFill(p.kind)
    out.push({
      type: 'rect',
      x: cx - COL_W / 2,
      y: cursorY,
      width: COL_W,
      height: HEAD_H,
      strokeColor: '#1e1e1e',
      fillColor: fill,
      fillStyle: 'solid',
      strokeWidth: 1,
      strokeStyle: 'solid',
      roughness: 0,
      opacity: 100,
      seed: hash(`zenuml-head-${p.id}`),
      version: 0,
      locked: false,
      angle: 0,
      zIndex: 0,
      groupIds: [],
      roundness: 2,
    } as CreateElementInput)
    out.push({
      type: 'text',
      x: cx - COL_W / 2 + 4,
      y: cursorY + (HEAD_H - 16) / 2,
      width: COL_W - 8,
      height: 16,
      text: p.id,
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
      seed: hash(`zenuml-head-label-${p.id}`),
      version: 0,
      locked: false,
      angle: 0,
      zIndex: 0,
      groupIds: [],
    } as CreateElementInput)
    // Lifeline: dashed vertical line down the column centre.
    out.push({
      type: 'line',
      x: cx,
      y: cursorY + HEAD_H,
      width: 0,
      height: lifelineBottom - cursorY - HEAD_H,
      points: [0, 0, 0, lifelineBottom - cursorY - HEAD_H],
      strokeColor: '#94a3b8',
      fillColor: 'transparent',
      fillStyle: 'none',
      strokeWidth: 1,
      strokeStyle: 'dashed',
      roughness: 0,
      opacity: 100,
      seed: hash(`zenuml-lifeline-${p.id}`),
      version: 0,
      locked: false,
      angle: 0,
      zIndex: 0,
      groupIds: [],
    } as CreateElementInput)
  })

  // Messages — one arrow per row.
  let rowY = cursorY + HEAD_H + TOP_PAD
  diagram.messages.forEach((m, idx) => {
    const fromX = cols.get(m.from)
    const toX = cols.get(m.to)
    if (fromX === undefined || toX === undefined) return
    const dx = toX - fromX
    out.push({
      type: 'arrow',
      x: fromX,
      y: rowY,
      width: dx,
      height: 0,
      points: [0, 0, dx, 0],
      strokeColor: '#1e1e1e',
      fillColor: 'transparent',
      fillStyle: 'none',
      strokeWidth: 1,
      strokeStyle: m.dashed ? 'dashed' : 'solid',
      roughness: 0,
      opacity: 100,
      seed: hash(`zenuml-msg-${idx}-${m.from}-${m.to}`),
      version: 0,
      locked: false,
      angle: 0,
      zIndex: 0,
      groupIds: [],
      startArrowhead: null,
      endArrowhead: m.isReturn ? 'arrow' : 'arrow',
    } as CreateElementInput)
    if (m.label) {
      out.push({
        type: 'text',
        x: Math.min(fromX, toX),
        y: rowY - 16,
        width: Math.abs(dx) || 80,
        height: 14,
        text: m.label,
        fontFamily: 'sans',
        fontSize: 11,
        textAlign: 'center',
        strokeColor: '#1e1e1e',
        fillColor: 'transparent',
        fillStyle: 'none',
        strokeWidth: 1,
        strokeStyle: 'solid',
        roughness: 0,
        opacity: 100,
        seed: hash(`zenuml-msg-label-${idx}-${m.from}-${m.to}`),
        version: 0,
        locked: false,
        angle: 0,
        zIndex: 0,
        groupIds: [],
      } as CreateElementInput)
    }
    rowY += ROW_H
  })

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
    seed: hash('zenuml-title'),
    version: 0,
    locked: false,
    angle: 0,
    zIndex: 0,
    groupIds: [],
  } as CreateElementInput
}

function pickFill(kind: ZenParticipantKind): string {
  switch (kind) {
    case 'Actor':
      return '#a5d8ff'
    case 'Boundary':
      return '#b2f2bb'
    case 'Control':
      return '#ffec99'
    case 'Entity':
      return '#ffd8a8'
    case 'Database':
      return '#e0a9f0'
    case 'Object':
      return '#fcc2d7'
  }
}

function hash(s: string): number {
  let h = 5381
  for (let i = 0; i < s.length; i++) h = (h * 33) ^ s.charCodeAt(i)
  return h >>> 0
}
