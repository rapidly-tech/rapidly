/**
 * Packet-diagram subset of Mermaid → Collab elements.
 *
 * Parses the Mermaid packet-beta syntax — title + bit-range rows
 * where each row is ``start-end: field_name`` (single-bit fields use
 * ``bit: name``) — and lays it out as a network-packet diagram with
 * 32-bit-wide rows and per-field cells whose width is proportional
 * to the bit count.
 *
 * What we handle
 * --------------
 *   ``packet-beta``                       — header (alias: ``packet``)
 *   ``title TCP Packet``                  — title
 *   ``0-15: Source Port``                 — bit-range field
 *   ``106: URG``                          — single-bit field
 *   ``32-63: Sequence Number``            — multi-row spans (bits
 *                                           wrap to the next row)
 *   ``%% comment`` lines                  — skipped
 *
 * Out of scope (decays to "ignored line"):
 *   - per-field colour overrides
 *   - markdown formatting in field labels
 *   - reverse / endianness annotations
 */

import type { CreateElementInput } from './element-store'

export interface PacketField {
  start: number
  end: number
  name: string
}

export interface PacketDiagram {
  title: string
  fields: PacketField[]
  /** Bit count per row of the rendered diagram. Defaults to 32
   *  which is the standard network-packet width but can be widened
   *  later via a config field if a future PR adds one. */
  bitsPerRow: number
}

/** Parse the packet source. Returns ``null`` when the input doesn't
 *  begin with ``packet`` so the caller can fall through to the
 *  generic "unsupported kind" message. */
export function parsePacket(source: string): PacketDiagram | null {
  const lines = source.split(/\r?\n/)
  let i = 0
  while (i < lines.length && !lines[i].trim()) i++
  const header = lines[i]?.trim() ?? ''
  if (!/^packet(?:-beta)?\b/i.test(header)) return null
  i++

  let title = ''
  const fields: PacketField[] = []

  for (; i < lines.length; i++) {
    const line = lines[i].split('%%')[0].trim()
    if (line.length === 0) continue

    const titleMatch = /^title\s+(.+)$/i.exec(line)
    if (titleMatch) {
      title = titleMatch[1].trim()
      continue
    }
    // Range field: ``start-end: name``.
    const rangeMatch = /^(\d+)\s*-\s*(\d+)\s*:\s*(.+)$/.exec(line)
    if (rangeMatch) {
      const start = Number(rangeMatch[1])
      const end = Number(rangeMatch[2])
      const name = rangeMatch[3].trim()
      if (end >= start) {
        fields.push({ start, end, name })
      }
      continue
    }
    // Single-bit field: ``bit: name``.
    const singleMatch = /^(\d+)\s*:\s*(.+)$/.exec(line)
    if (singleMatch) {
      const bit = Number(singleMatch[1])
      fields.push({ start: bit, end: bit, name: singleMatch[2].trim() })
      continue
    }
    // Unrecognised — silently skip.
  }

  return { title, fields, bitsPerRow: 32 }
}

const ROW_WIDTH = 640
const ROW_HEIGHT = 50
const ROW_GAP = 4
const TITLE_HEIGHT = 28
const TICK_HEIGHT = 18

export interface PacketLayoutOptions {
  originX?: number
  originY?: number
}

/** Lay out the parsed diagram and emit Collab element inputs. Each
 *  field is rendered as one or more rect cells across the
 *  ``bitsPerRow`` rows, with the field name centred inside. */
export function packetToElements(
  diagram: PacketDiagram,
  options: PacketLayoutOptions = {},
): CreateElementInput[] {
  const ox = options.originX ?? 0
  const oy = options.originY ?? 0
  const out: CreateElementInput[] = []

  if (diagram.fields.length === 0) {
    if (diagram.title) {
      out.push(makeTitle(diagram.title, ox, oy))
    }
    return out
  }

  const bitsPerRow = Math.max(1, diagram.bitsPerRow)
  const bitWidth = ROW_WIDTH / bitsPerRow

  // Title.
  let cursorY = oy
  if (diagram.title) {
    out.push(makeTitle(diagram.title, ox, cursorY))
    cursorY += TITLE_HEIGHT
  }

  // Bit ruler — render tick labels every 8 bits across the top of
  // the first row.
  const rulerY = cursorY
  for (let b = 0; b < bitsPerRow; b += 8) {
    out.push({
      type: 'text',
      x: ox + b * bitWidth - 12,
      y: rulerY,
      width: 24,
      height: 12,
      text: String(b),
      fontFamily: 'mono',
      fontSize: 10,
      textAlign: 'left',
      strokeColor: '#475569',
      fillColor: 'transparent',
      fillStyle: 'none',
      strokeWidth: 1,
      strokeStyle: 'solid',
      roughness: 0,
      opacity: 100,
      seed: hash(`packet-tick-${b}`),
      version: 0,
      locked: false,
      angle: 0,
      zIndex: 0,
      groupIds: [],
    } as CreateElementInput)
  }
  cursorY += TICK_HEIGHT

  // Walk every field, emitting one rect per row it spans. A field
  // whose range crosses a row boundary splits into multiple cells
  // sharing the same fill colour + label.
  diagram.fields.forEach((field, idx) => {
    const fill = pickFill(idx)
    let bit = field.start
    while (bit <= field.end) {
      const row = Math.floor(bit / bitsPerRow)
      const colInRow = bit % bitsPerRow
      const rowEndBit = (row + 1) * bitsPerRow - 1
      const segmentEnd = Math.min(field.end, rowEndBit)
      const widthBits = segmentEnd - bit + 1
      const cellX = ox + colInRow * bitWidth
      const cellY = cursorY + row * (ROW_HEIGHT + ROW_GAP)
      const cellW = widthBits * bitWidth
      out.push({
        type: 'rect',
        x: cellX,
        y: cellY,
        width: cellW,
        height: ROW_HEIGHT,
        strokeColor: '#1e1e1e',
        fillColor: fill,
        fillStyle: 'solid',
        strokeWidth: 1,
        strokeStyle: 'solid',
        roughness: 0,
        opacity: 100,
        seed: hash(`packet-field-${idx}-${bit}`),
        version: 0,
        locked: false,
        angle: 0,
        zIndex: 0,
        groupIds: [],
        roundness: 2,
      } as CreateElementInput)
      // Cell label — name + bit range so a wrapped segment still
      // reads as part of the same field.
      const labelText =
        field.start === field.end
          ? `${field.name} (${field.start})`
          : `${field.name} (${field.start}–${field.end})`
      out.push({
        type: 'text',
        x: cellX + 4,
        y: cellY + (ROW_HEIGHT - 16) / 2,
        width: cellW - 8,
        height: 16,
        text: labelText,
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
        seed: hash(`packet-field-label-${idx}-${bit}`),
        version: 0,
        locked: false,
        angle: 0,
        zIndex: 0,
        groupIds: [],
      } as CreateElementInput)
      bit = segmentEnd + 1
    }
  })

  return out
}

function makeTitle(text: string, ox: number, oy: number): CreateElementInput {
  return {
    type: 'text',
    x: ox,
    y: oy,
    width: ROW_WIDTH,
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
    seed: hash('packet-title'),
    version: 0,
    locked: false,
    angle: 0,
    zIndex: 0,
    groupIds: [],
  } as CreateElementInput
}

const FIELD_PALETTE = [
  '#a5d8ff',
  '#ffec99',
  '#b2f2bb',
  '#ffc9c9',
  '#e0a9f0',
  '#fcc2d7',
  '#c0eb75',
  '#ffd8a8',
  '#a5fbe1',
  '#bac8ff',
] as const

function pickFill(idx: number): string {
  return FIELD_PALETTE[idx % FIELD_PALETTE.length]
}

function hash(s: string): number {
  let h = 5381
  for (let i = 0; i < s.length; i++) h = (h * 33) ^ s.charCodeAt(i)
  return h >>> 0
}
