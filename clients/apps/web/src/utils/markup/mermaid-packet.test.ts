import { describe, expect, it } from 'vitest'

import { packetToElements, parsePacket } from './mermaid-packet'

describe('parsePacket', () => {
  it('returns null when the source is not a packet diagram', () => {
    expect(parsePacket('flowchart TD\nA --> B')).toBeNull()
    expect(parsePacket('')).toBeNull()
  })

  it('accepts both packet and packet-beta headers', () => {
    expect(parsePacket('packet\n0-15: src')).not.toBeNull()
    expect(parsePacket('packet-beta\n0-15: src')).not.toBeNull()
  })

  it('parses bit ranges + single-bit fields', () => {
    const d = parsePacket(`packet-beta
      0-15: Source Port
      16-31: Destination Port
      106: URG`)!
    expect(d.fields).toEqual([
      { start: 0, end: 15, name: 'Source Port' },
      { start: 16, end: 31, name: 'Destination Port' },
      { start: 106, end: 106, name: 'URG' },
    ])
  })

  it('captures the title', () => {
    const d = parsePacket('packet-beta\ntitle TCP Packet')!
    expect(d.title).toBe('TCP Packet')
  })

  it('drops malformed ranges where end < start', () => {
    const d = parsePacket('packet-beta\n10-5: bad')!
    expect(d.fields).toEqual([])
  })

  it('skips comments + tolerates trailing comments', () => {
    const d = parsePacket(`packet-beta
      %% intro
      0-7: A %% trailing`)!
    expect(d.fields).toHaveLength(1)
  })

  it('ignores garbled lines without aborting', () => {
    const d = parsePacket(`packet-beta
      0-3: A
      garbled+++
      4-7: B`)!
    expect(d.fields).toHaveLength(2)
  })
})

describe('packetToElements', () => {
  it('emits one rect + label per single-row field', () => {
    const d = parsePacket(`packet-beta
      0-15: Source Port
      16-31: Destination Port`)!
    const els = packetToElements(d)
    expect(els.filter((e) => e.type === 'rect')).toHaveLength(2)
  })

  it('splits a multi-row field across rows', () => {
    // A 64-bit field starting at 0 spans 2 rows of 32 bits each, so
    // it should produce 2 rect cells (and 2 labels).
    const d = parsePacket('packet-beta\n0-63: Sequence Number')!
    const els = packetToElements(d)
    expect(els.filter((e) => e.type === 'rect')).toHaveLength(2)
  })

  it('makes a wider field render wider than a narrower one', () => {
    const d = parsePacket(`packet-beta
      0-15: Wide
      16-23: Narrow`)!
    const els = packetToElements(d)
    const rects = els.filter((e) => e.type === 'rect') as Array<{
      width: number
    }>
    expect(rects[0].width).toBeGreaterThan(rects[1].width)
  })

  it('renders title above the diagram when set', () => {
    const d = parsePacket('packet-beta\ntitle TCP\n0-7: A')!
    const els = packetToElements(d)
    const titles = els.filter(
      (e) =>
        e.type === 'text' && (e as unknown as { text: string }).text === 'TCP',
    )
    expect(titles).toHaveLength(1)
  })

  it('emits bit-position ruler ticks across the top', () => {
    const d = parsePacket('packet-beta\n0-31: Header')!
    const els = packetToElements(d)
    const tickTexts = els
      .filter(
        (e) =>
          e.type === 'text' &&
          (e as unknown as { fontFamily: string }).fontFamily === 'mono',
      )
      .map((e) => (e as unknown as { text: string }).text)
    // Ticks every 8 bits across a 32-bit row → 0, 8, 16, 24.
    expect(tickTexts).toEqual(['0', '8', '16', '24'])
  })

  it('respects originX / originY', () => {
    const d = parsePacket('packet-beta\n0-7: A')!
    const els = packetToElements(d, { originX: 500, originY: 300 })
    const rect = els.find((e) => e.type === 'rect') as { x: number; y: number }
    expect(rect.x).toBeGreaterThanOrEqual(500)
    expect(rect.y).toBeGreaterThanOrEqual(300)
  })

  it('produces deterministic output for a given input', () => {
    const a = packetToElements(parsePacket('packet-beta\n0-15: A\n16-31: B')!)
    const b = packetToElements(parsePacket('packet-beta\n0-15: A\n16-31: B')!)
    expect(JSON.stringify(a)).toBe(JSON.stringify(b))
  })

  it('renders nothing meaningful for an empty diagram', () => {
    const d = parsePacket('packet-beta\n%% no fields')!
    const els = packetToElements(d)
    // No fields → no cells. Title-only would emit one text but our
    // empty source has no title either.
    expect(els).toEqual([])
  })
})
