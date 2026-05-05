/**
 * Sequence-diagram subset of Mermaid → Collab elements.
 *
 * Parses the common-case sequence syntax — participants, four
 * message-arrow variants, ``Note`` lines — and lays it out as a
 * standard sequence diagram: participants as labelled rect headers
 * across the top, dashed vertical lifelines, messages as horizontal
 * arrows between lifelines at progressively-lower y positions, notes
 * as small rect blocks.
 *
 * What we handle
 * --------------
 *   ``sequenceDiagram``                — header
 *   ``participant A``                  — declares a lifeline
 *   ``participant Bob as B``           — alias form
 *   ``A->>B: Hello``                   — solid arrow (sync)
 *   ``A-->>B: Reply``                  — dashed arrow (async / return)
 *   ``A->B: msg``                      — solid line, no arrow head
 *   ``A-->B: msg``                     — dashed line, no arrow head
 *   ``Note right of A: text``          — note next to a participant
 *   ``Note left of A: text``
 *   ``Note over A,B: text``            — note spanning two participants
 *   ``%% comment`` lines               — skipped
 *
 * Out of scope (decays harmlessly to "ignored line"): activate /
 * deactivate, loops, alt / opt blocks, par, critical, break,
 * autonumber, links, custom font config. Each of those is a
 * meaningful subsystem and they all extend the layout — the v1 here
 * captures the visual essence.
 */

import type { CreateElementInput } from './element-store'

export interface SequenceParticipant {
  /** Internal id used by message references. */
  id: string
  /** Display label shown on the header rect. */
  label: string
}

export type SequenceArrow = 'solid-arrow' | 'dashed-arrow' | 'solid' | 'dashed'

export interface SequenceMessage {
  kind: 'message'
  from: string
  to: string
  arrow: SequenceArrow
  label: string
}

export type NotePosition = 'left' | 'right' | 'over'

export interface SequenceNote {
  kind: 'note'
  position: NotePosition
  /** Always at least one participant id; ``over A,B`` carries two. */
  participantIds: string[]
  text: string
}

export type SequenceEvent = SequenceMessage | SequenceNote

export interface SequenceDiagram {
  participants: SequenceParticipant[]
  events: SequenceEvent[]
}

/** Parse the sequence-diagram source. Returns ``null`` when the input
 *  doesn't start with ``sequenceDiagram`` so the caller can fall
 *  through to the generic "unsupported kind" message. */
export function parseSequence(source: string): SequenceDiagram | null {
  const lines = source.split(/\r?\n/)
  let i = 0
  while (i < lines.length && !lines[i].trim()) i++
  const header = lines[i]?.trim() ?? ''
  if (!/^sequenceDiagram\b/i.test(header)) return null
  i++

  const participants: SequenceParticipant[] = []
  const events: SequenceEvent[] = []
  // Auto-declare participants the first time they appear in a
  // message — matches Mermaid's lenient behaviour where you can
  // write ``A->>B: hi`` without explicitly listing A or B.
  const seen = new Set<string>()
  const ensure = (id: string, label?: string) => {
    if (seen.has(id)) {
      if (label) {
        const existing = participants.find((p) => p.id === id)
        if (existing) existing.label = label
      }
      return
    }
    seen.add(id)
    participants.push({ id, label: label ?? id })
  }

  for (; i < lines.length; i++) {
    const line = lines[i].split('%%')[0].trim()
    if (line.length === 0) continue

    // ``participant A`` or ``participant A as Alice``
    const partMatch = /^participant\s+(\S+)(?:\s+as\s+(.+))?$/i.exec(line)
    if (partMatch) {
      ensure(partMatch[1], partMatch[2]?.trim())
      continue
    }
    // ``actor`` is the same shape — we render it as a rect for v1.
    const actorMatch = /^actor\s+(\S+)(?:\s+as\s+(.+))?$/i.exec(line)
    if (actorMatch) {
      ensure(actorMatch[1], actorMatch[2]?.trim())
      continue
    }

    // Notes — ``Note right of A: …``, ``Note left of A: …``, or
    // ``Note over A,B: …``.
    const noteOver = /^Note\s+over\s+([^:]+)\s*:\s*(.+)$/i.exec(line)
    if (noteOver) {
      const ids = noteOver[1]
        .split(',')
        .map((s) => s.trim())
        .filter(Boolean)
      ids.forEach((id) => ensure(id))
      events.push({
        kind: 'note',
        position: 'over',
        participantIds: ids,
        text: noteOver[2].trim(),
      })
      continue
    }
    const noteSide = /^Note\s+(left|right)\s+of\s+(\S+)\s*:\s*(.+)$/i.exec(line)
    if (noteSide) {
      ensure(noteSide[2])
      events.push({
        kind: 'note',
        position: noteSide[1].toLowerCase() as NotePosition,
        participantIds: [noteSide[2]],
        text: noteSide[3].trim(),
      })
      continue
    }

    // Messages: ordered longest-first so ``-->>`` doesn't get
    // mistaken for ``-->``. Participant ids are restricted to word
    // chars (letters / digits / underscore) so ``\w+`` doesn't
    // greedily consume the leading ``-`` of the operator and end up
    // with ``from = 'A-'``.
    const messageMatch = /^(\w+)\s*(-->>|->>|-->|->)\s*(\w+)\s*:\s*(.+)$/.exec(
      line,
    )
    if (messageMatch) {
      const from = messageMatch[1]
      const op = messageMatch[2]
      const to = messageMatch[3]
      const label = messageMatch[4].trim()
      ensure(from)
      ensure(to)
      const arrow: SequenceArrow =
        op === '-->>'
          ? 'dashed-arrow'
          : op === '->>'
            ? 'solid-arrow'
            : op === '-->'
              ? 'dashed'
              : 'solid'
      events.push({ kind: 'message', from, to, arrow, label })
      continue
    }
    // Unrecognised line: skip silently — a strict parser would lose
    // the user's whole diagram over a single typo, which feels worse
    // than degrading the surrounding output.
  }

  return { participants, events }
}

const PARTICIPANT_WIDTH = 120
const PARTICIPANT_HEIGHT = 40
const PARTICIPANT_GAP = 60
const EVENT_GAP = 50
const TOP_PADDING = 40
const NOTE_HEIGHT = 36
const NOTE_PADDING = 12

export interface SequenceLayoutOptions {
  originX?: number
  originY?: number
}

/** Lay the parsed diagram out and emit Collab element inputs. The
 *  caller passes the result to ``store.create()`` per element inside
 *  one transaction (consistent with how the flowchart importer works
 *  in ``mermaid.ts``).
 *
 *  Layout
 *  ------
 *   - Participants spread left-to-right at the top, each ``PARTICIPANT_
 *     WIDTH + PARTICIPANT_GAP`` apart.
 *   - Lifelines drop straight down from each participant's centre as
 *     dashed vertical lines.
 *   - Each event takes one horizontal slot ``EVENT_GAP`` apart down
 *     the y-axis.
 *   - Messages render as arrow / line elements between the from and
 *     to lifelines. Self-message (``A->>A``) draws a small loop arrow.
 *   - Notes render as filled rect with text centred on top. ``over``
 *     spans both participants; ``left``/``right`` sits next to the
 *     named one.
 */
export function sequenceToElements(
  diagram: SequenceDiagram,
  options: SequenceLayoutOptions = {},
): CreateElementInput[] {
  const ox = options.originX ?? 0
  const oy = options.originY ?? 0
  const out: CreateElementInput[] = []

  // x-coordinate of each participant's *centre*. Stored by id so
  // messages + notes can look up a target without a linear scan.
  const cx = new Map<string, number>()
  diagram.participants.forEach((p, idx) => {
    const x =
      ox + idx * (PARTICIPANT_WIDTH + PARTICIPANT_GAP) + PARTICIPANT_WIDTH / 2
    cx.set(p.id, x)
  })

  // Total diagram height — used to draw lifelines that span every
  // event row. Headers sit at oy; events start one EVENT_GAP below.
  const totalEvents = diagram.events.length
  const lifelineTop = oy + PARTICIPANT_HEIGHT + 4
  const lifelineBottom =
    lifelineTop + TOP_PADDING + Math.max(1, totalEvents) * EVENT_GAP

  // Participant headers + lifelines.
  for (const p of diagram.participants) {
    const x = (cx.get(p.id) ?? ox) - PARTICIPANT_WIDTH / 2
    out.push({
      type: 'rect',
      x,
      y: oy,
      width: PARTICIPANT_WIDTH,
      height: PARTICIPANT_HEIGHT,
      strokeColor: '#1e1e1e',
      fillColor: '#e9ecef',
      fillStyle: 'solid',
      strokeWidth: 1,
      strokeStyle: 'solid',
      roughness: 0,
      opacity: 100,
      seed: hash(p.id),
      version: 0,
      locked: false,
      angle: 0,
      zIndex: 0,
      groupIds: [],
      roundness: 8,
    } as CreateElementInput)
    // Header label (centred in the rect).
    out.push({
      type: 'text',
      x: x + 8,
      y: oy + (PARTICIPANT_HEIGHT - 18) / 2,
      width: PARTICIPANT_WIDTH - 16,
      height: 18,
      text: p.label,
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
      seed: hash('label-' + p.id),
      version: 0,
      locked: false,
      angle: 0,
      zIndex: 0,
      groupIds: [],
    } as CreateElementInput)
    // Lifeline.
    const lx = cx.get(p.id) ?? ox
    out.push({
      type: 'line',
      x: lx,
      y: lifelineTop,
      width: 0,
      height: lifelineBottom - lifelineTop,
      points: [0, 0, 0, lifelineBottom - lifelineTop],
      strokeColor: '#94a3b8',
      fillColor: 'transparent',
      fillStyle: 'none',
      strokeWidth: 1,
      strokeStyle: 'dashed',
      roughness: 0,
      opacity: 100,
      seed: hash('lifeline-' + p.id),
      version: 0,
      locked: false,
      angle: 0,
      zIndex: 0,
      groupIds: [],
    } as CreateElementInput)
  }

  // Events — messages + notes, walked in source order.
  diagram.events.forEach((event, idx) => {
    const y = lifelineTop + TOP_PADDING + idx * EVENT_GAP
    if (event.kind === 'message') {
      const fx = cx.get(event.from)
      const tx = cx.get(event.to)
      if (fx === undefined || tx === undefined) return
      // Self-message (A->>A) — draw a small right-going loop.
      if (event.from === event.to) {
        const loopW = 50
        const loopH = 24
        out.push({
          type: 'arrow',
          x: fx,
          y,
          width: loopW,
          height: loopH,
          points: [0, 0, loopW, 0, loopW, loopH, 0, loopH],
          startArrowhead: null,
          endArrowhead:
            event.arrow === 'solid-arrow' || event.arrow === 'dashed-arrow'
              ? 'triangle'
              : null,
          strokeColor: '#1e1e1e',
          fillColor: 'transparent',
          fillStyle: 'none',
          strokeWidth: 1,
          strokeStyle:
            event.arrow === 'dashed' || event.arrow === 'dashed-arrow'
              ? 'dashed'
              : 'solid',
          roughness: 0,
          opacity: 100,
          seed: hash(`msg-${idx}`),
          version: 0,
          locked: false,
          angle: 0,
          zIndex: 0,
          groupIds: [],
        } as CreateElementInput)
      } else {
        const minX = Math.min(fx, tx)
        const maxX = Math.max(fx, tx)
        const width = maxX - minX
        const goingRight = tx > fx
        out.push({
          type: 'arrow',
          x: minX,
          y,
          width,
          height: 0,
          points: goingRight ? [0, 0, width, 0] : [width, 0, 0, 0],
          startArrowhead: null,
          endArrowhead:
            event.arrow === 'solid-arrow' || event.arrow === 'dashed-arrow'
              ? 'triangle'
              : null,
          strokeColor: '#1e1e1e',
          fillColor: 'transparent',
          fillStyle: 'none',
          strokeWidth: 1,
          strokeStyle:
            event.arrow === 'dashed' || event.arrow === 'dashed-arrow'
              ? 'dashed'
              : 'solid',
          roughness: 0,
          opacity: 100,
          seed: hash(`msg-${idx}`),
          version: 0,
          locked: false,
          angle: 0,
          zIndex: 0,
          groupIds: [],
        } as CreateElementInput)
      }
      // Label text above the arrow.
      const lx = (fx + tx) / 2
      out.push({
        type: 'text',
        x: lx - 80,
        y: y - 18,
        width: 160,
        height: 16,
        text: event.label,
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
        seed: hash(`msg-label-${idx}`),
        version: 0,
        locked: false,
        angle: 0,
        zIndex: 0,
        groupIds: [],
      } as CreateElementInput)
      return
    }
    // Note.
    const ids = event.participantIds.map((id) => cx.get(id) ?? 0)
    if (ids.length === 0) return
    let nx: number
    let nw: number
    if (event.position === 'over') {
      const minX = Math.min(...ids) - PARTICIPANT_WIDTH / 2 + NOTE_PADDING
      const maxX = Math.max(...ids) + PARTICIPANT_WIDTH / 2 - NOTE_PADDING
      nx = minX
      nw = Math.max(80, maxX - minX)
    } else if (event.position === 'right') {
      nx = ids[0] + PARTICIPANT_WIDTH / 2 + NOTE_PADDING
      nw = 120
    } else {
      nx = ids[0] - PARTICIPANT_WIDTH / 2 - NOTE_PADDING - 120
      nw = 120
    }
    out.push({
      type: 'rect',
      x: nx,
      y: y - NOTE_HEIGHT / 2,
      width: nw,
      height: NOTE_HEIGHT,
      strokeColor: '#92400e',
      fillColor: '#fef3c7',
      fillStyle: 'solid',
      strokeWidth: 1,
      strokeStyle: 'solid',
      roughness: 0,
      opacity: 100,
      seed: hash(`note-${idx}`),
      version: 0,
      locked: false,
      angle: 0,
      zIndex: 0,
      groupIds: [],
      roundness: 4,
    } as CreateElementInput)
    out.push({
      type: 'text',
      x: nx + 6,
      y: y - 9,
      width: nw - 12,
      height: 18,
      text: event.text,
      fontFamily: 'sans',
      fontSize: 12,
      textAlign: 'center',
      strokeColor: '#92400e',
      fillColor: 'transparent',
      fillStyle: 'none',
      strokeWidth: 1,
      strokeStyle: 'solid',
      roughness: 0,
      opacity: 100,
      seed: hash(`note-text-${idx}`),
      version: 0,
      locked: false,
      angle: 0,
      zIndex: 0,
      groupIds: [],
    } as CreateElementInput)
  })

  return out
}

/** Stable seed for a string, just for the rough renderer's per-shape
 *  randomness. djb2-like — fine for a non-crypto sentinel. */
function hash(s: string): number {
  let h = 5381
  for (let i = 0; i < s.length; i++) h = (h * 33) ^ s.charCodeAt(i)
  return h >>> 0
}
