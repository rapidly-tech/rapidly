import { describe, expect, it } from 'vitest'

import { parseSequence, sequenceToElements } from './mermaid-sequence'

describe('parseSequence', () => {
  it('returns null when the source is not a sequence diagram', () => {
    expect(parseSequence('flowchart TD\nA --> B')).toBeNull()
    expect(parseSequence('')).toBeNull()
    expect(parseSequence('hello world')).toBeNull()
  })

  it('parses the minimal explicit-participant case', () => {
    const d = parseSequence(`sequenceDiagram
      participant A
      participant B
      A->>B: Hello`)!
    expect(d.participants.map((p) => p.id)).toEqual(['A', 'B'])
    expect(d.events).toHaveLength(1)
    const msg = d.events[0]
    expect(msg.kind).toBe('message')
    if (msg.kind === 'message') {
      expect(msg.from).toBe('A')
      expect(msg.to).toBe('B')
      expect(msg.arrow).toBe('solid-arrow')
      expect(msg.label).toBe('Hello')
    }
  })

  it('honours the "as" alias on participants', () => {
    const d = parseSequence(`sequenceDiagram
      participant A as Alice
      participant B as Bob
      A->>B: Hi`)!
    expect(d.participants.map((p) => p.label)).toEqual(['Alice', 'Bob'])
  })

  it('auto-declares participants the first time a message references them', () => {
    const d = parseSequence(`sequenceDiagram
      A->>B: ping
      B-->>A: pong`)!
    expect(d.participants.map((p) => p.id).sort()).toEqual(['A', 'B'])
  })

  it('distinguishes the four arrow variants', () => {
    const d = parseSequence(`sequenceDiagram
      A->>B: a
      A-->>B: b
      A->B: c
      A-->B: d`)!
    expect(
      d.events.map((e) => (e.kind === 'message' ? e.arrow : null)),
    ).toEqual(['solid-arrow', 'dashed-arrow', 'solid', 'dashed'])
  })

  it('parses notes — left of, right of, over', () => {
    const d = parseSequence(`sequenceDiagram
      participant A
      participant B
      Note left of A: lefty
      Note right of B: righty
      Note over A,B: shared`)!
    const notes = d.events.filter((e) => e.kind === 'note')
    expect(notes).toHaveLength(3)
    expect(notes[0].kind === 'note' && notes[0].position).toBe('left')
    expect(notes[1].kind === 'note' && notes[1].position).toBe('right')
    expect(notes[2].kind === 'note' && notes[2].position).toBe('over')
    expect(notes[2].kind === 'note' && notes[2].participantIds).toEqual([
      'A',
      'B',
    ])
  })

  it('skips comment lines + tolerates trailing comments', () => {
    const d = parseSequence(`sequenceDiagram
      %% comment
      participant A
      A->>A: self %% trailing`)!
    expect(d.participants.map((p) => p.id)).toEqual(['A'])
    expect(d.events).toHaveLength(1)
    expect(d.events[0].kind === 'message' && d.events[0].label).toBe('self')
  })

  it('treats actor as participant', () => {
    const d = parseSequence('sequenceDiagram\nactor User')!
    expect(d.participants).toHaveLength(1)
    expect(d.participants[0].id).toBe('User')
  })

  it('ignores unrecognised lines without aborting', () => {
    const d = parseSequence(`sequenceDiagram
      participant A
      activate A
      garbled+++line
      A->>A: still parsed`)!
    expect(d.events).toHaveLength(1)
  })
})

describe('sequenceToElements', () => {
  it('emits header rect + label + lifeline per participant', () => {
    const d = parseSequence(`sequenceDiagram
      participant A
      participant B
      A->>B: hi`)!
    const els = sequenceToElements(d)
    // 2 participants × (rect + label + lifeline) = 6, plus 1 message
    // arrow + 1 message label = 8 total.
    expect(els).toHaveLength(8)
    const lifelines = els.filter(
      (e) => e.type === 'line' && e.strokeStyle === 'dashed',
    )
    expect(lifelines).toHaveLength(2)
  })

  it('renders self-message as a small loop arrow', () => {
    const d = parseSequence(`sequenceDiagram
      participant A
      A->>A: think`)!
    const els = sequenceToElements(d)
    const loops = els.filter((e) => e.type === 'arrow')
    expect(loops).toHaveLength(1)
    // Self-loop's points polyline carries 4 vertices (8 numbers), not 2.
    expect(
      (loops[0] as unknown as { points: number[] }).points.length,
    ).toBe(8)
  })

  it('respects the originX / originY offset', () => {
    const d = parseSequence(`sequenceDiagram
      participant A
      A->>A: x`)!
    const els = sequenceToElements(d, { originX: 500, originY: 300 })
    const header = els.find((e) => e.type === 'rect') as {
      x: number
      y: number
    }
    expect(header.x).toBeGreaterThanOrEqual(500)
    expect(header.y).toBe(300)
  })

  it('produces no message elements when the diagram has no events', () => {
    const d = parseSequence(`sequenceDiagram
      participant A`)!
    const els = sequenceToElements(d)
    // 1 participant → rect + label + lifeline = 3.
    expect(els).toHaveLength(3)
    expect(els.find((e) => e.type === 'arrow')).toBeUndefined()
  })

  it('produces note rects + labels for note events', () => {
    const d = parseSequence(`sequenceDiagram
      participant A
      Note right of A: hello`)!
    const els = sequenceToElements(d)
    // header rect + header text + lifeline + note rect + note text = 5.
    expect(els).toHaveLength(5)
    const noteRects = els.filter(
      (e) =>
        e.type === 'rect' &&
        (e as { fillColor?: string }).fillColor === '#fef3c7',
    )
    expect(noteRects).toHaveLength(1)
  })
})
