import { describe, expect, it } from 'vitest'

import { journeyToElements, parseJourney } from './mermaid-journey'

describe('parseJourney', () => {
  it('returns null when the source is not a journey', () => {
    expect(parseJourney('flowchart TD\nA --> B')).toBeNull()
    expect(parseJourney('')).toBeNull()
  })

  it('parses a minimal journey', () => {
    const d = parseJourney(`journey
      title My day
      section Morning
      Make coffee: 5: Me`)!
    expect(d.title).toBe('My day')
    expect(d.sections).toEqual(['Morning'])
    expect(d.tasks).toHaveLength(1)
    const t = d.tasks[0]
    expect(t.name).toBe('Make coffee')
    expect(t.score).toBe(5)
    expect(t.actors).toEqual(['Me'])
    expect(t.section).toBe('Morning')
  })

  it('captures multiple actors via comma-separated list', () => {
    const d = parseJourney(`journey
      Read mail: 2: Me, Coworker, Boss`)!
    expect(d.tasks[0].actors).toEqual(['Me', 'Coworker', 'Boss'])
  })

  it('makes the actor list optional', () => {
    const d = parseJourney('journey\nStandup: 3')!
    expect(d.tasks[0].actors).toEqual([])
    expect(d.tasks[0].score).toBe(3)
  })

  it('records sections in source order without duplicates', () => {
    const d = parseJourney(`journey
      section Morning
      Wake up: 4
      section Work
      Standup: 3
      section Morning
      Stretch: 5`)!
    expect(d.sections).toEqual(['Morning', 'Work'])
  })

  it('skips comments + tolerates trailing comments', () => {
    const d = parseJourney(`journey
      %% start
      title T
      Task A: 5: Me %% trailing`)!
    expect(d.title).toBe('T')
    expect(d.tasks).toHaveLength(1)
  })

  it('ignores garbled lines without aborting', () => {
    const d = parseJourney(`journey
      Task A: 5: Me
      garbled+++
      Task B: 1: Me`)!
    expect(d.tasks).toHaveLength(2)
  })
})

describe('journeyToElements', () => {
  it('emits a title text + section header + task cell', () => {
    const d = parseJourney(`journey
      title Hello
      section Morning
      Wake up: 5: Me`)!
    const els = journeyToElements(d)
    const texts = els.filter((e) => e.type === 'text')
    const titles = texts.filter(
      (e) => (e as unknown as { text: string }).text === 'Hello',
    )
    expect(titles).toHaveLength(1)
    const sectionHeaders = texts.filter(
      (e) => (e as unknown as { text: string }).text === 'Morning',
    )
    expect(sectionHeaders).toHaveLength(1)
    const rects = els.filter((e) => e.type === 'rect')
    expect(rects).toHaveLength(1)
  })

  it('emits one rect per task in source order', () => {
    const d = parseJourney(`journey
      section S
      A: 5
      B: 3
      C: 1`)!
    const els = journeyToElements(d)
    expect(els.filter((e) => e.type === 'rect')).toHaveLength(3)
  })

  it('renders score chips as ★/☆ characters reflecting the value', () => {
    const d = parseJourney(`journey
      A: 5
      B: 3
      C: 0`)!
    const els = journeyToElements(d)
    const texts = els
      .filter((e) => e.type === 'text')
      .map((e) => (e as unknown as { text: string }).text)
    expect(texts).toContain('★★★★★')
    expect(texts).toContain('★★★☆☆')
    expect(texts).toContain('☆☆☆☆☆')
  })

  it('clamps out-of-range scores into 0..5', () => {
    const d = parseJourney(`journey
      A: 9
      B: -2`)!
    const els = journeyToElements(d)
    const texts = els
      .filter((e) => e.type === 'text')
      .map((e) => (e as unknown as { text: string }).text)
    expect(texts).toContain('★★★★★') // 9 clamps to 5
    expect(texts).toContain('☆☆☆☆☆') // -2 clamps to 0
  })

  it('respects the originX / originY offset', () => {
    const d = parseJourney('journey\nA: 5: Me')!
    const els = journeyToElements(d, { originX: 500, originY: 300 })
    const rect = els.find((e) => e.type === 'rect') as { x: number; y: number }
    expect(rect.x).toBeGreaterThanOrEqual(500)
    expect(rect.y).toBeGreaterThanOrEqual(300)
  })

  it('places sections side-by-side with a gap', () => {
    const d = parseJourney(`journey
      section A
      Task1: 5
      section B
      Task2: 5`)!
    const els = journeyToElements(d)
    const rects = els.filter((e) => e.type === 'rect') as Array<{ x: number }>
    expect(rects).toHaveLength(2)
    expect(rects[1].x).toBeGreaterThan(rects[0].x + 100)
  })

  it('produces deterministic output for a given input', () => {
    const a = journeyToElements(parseJourney(`journey\nsection S\nA: 5\nB: 3`)!)
    const b = journeyToElements(parseJourney(`journey\nsection S\nA: 5\nB: 3`)!)
    expect(JSON.stringify(a)).toBe(JSON.stringify(b))
  })
})
