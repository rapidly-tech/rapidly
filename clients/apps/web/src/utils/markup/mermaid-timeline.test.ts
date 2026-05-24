import { describe, expect, it } from 'vitest'

import { parseTimeline, timelineToElements } from './mermaid-timeline'

describe('parseTimeline', () => {
  it('returns null when the source is not a timeline', () => {
    expect(parseTimeline('flowchart TD\nA --> B')).toBeNull()
    expect(parseTimeline('')).toBeNull()
  })

  it('parses a minimal timeline', () => {
    const d = parseTimeline(`timeline
      title History
      2002 : LinkedIn`)!
    expect(d.title).toBe('History')
    expect(d.periods).toEqual([
      { label: '2002', events: ['LinkedIn'], section: '' },
    ])
  })

  it('captures multiple events per period (chained colons)', () => {
    const d = parseTimeline('timeline\n2004 : Facebook : Google')!
    expect(d.periods[0].events).toEqual(['Facebook', 'Google'])
  })

  it('groups periods by section', () => {
    const d = parseTimeline(`timeline
      section 2000s
      2002 : LinkedIn
      section 2010s
      2010 : Instagram`)!
    expect(d.sections).toEqual(['2000s', '2010s'])
    expect(d.periods[0].section).toBe('2000s')
    expect(d.periods[1].section).toBe('2010s')
  })

  it('accepts a bare period without events', () => {
    const d = parseTimeline('timeline\n2003')!
    expect(d.periods).toEqual([{ label: '2003', events: [], section: '' }])
  })

  it('skips comments + tolerates trailing comments', () => {
    const d = parseTimeline(`timeline
      %% intro
      title T
      2001 : A %% trailing`)!
    expect(d.title).toBe('T')
    expect(d.periods).toHaveLength(1)
  })

  it('ignores garbled lines without aborting', () => {
    const d = parseTimeline(`timeline
      2001 : A
      garbled +++
      2002 : B`)!
    expect(d.periods).toHaveLength(2)
  })
})

describe('timelineToElements', () => {
  it('emits a title text + axis line + tick + period label', () => {
    const d = parseTimeline(`timeline
      title T
      2001 : A`)!
    const els = timelineToElements(d)
    const texts = els.filter((e) => e.type === 'text')
    const titles = texts.filter(
      (e) => (e as unknown as { text: string }).text === 'T',
    )
    expect(titles).toHaveLength(1)
    const lines = els.filter((e) => e.type === 'line')
    expect(lines).toHaveLength(1) // the axis
    const ellipses = els.filter((e) => e.type === 'ellipse')
    expect(ellipses).toHaveLength(1) // the tick
  })

  it('emits one rect + label per event', () => {
    const d = parseTimeline('timeline\n2004 : Facebook : Google')!
    const els = timelineToElements(d)
    expect(els.filter((e) => e.type === 'rect')).toHaveLength(2)
  })

  it('renders section headers when sections are declared', () => {
    const d = parseTimeline(`timeline
      section 2000s
      2002 : A
      section 2010s
      2010 : B`)!
    const els = timelineToElements(d)
    const sectionLabels = els
      .filter((e) => e.type === 'text')
      .map((e) => (e as unknown as { text: string }).text)
    expect(sectionLabels).toContain('2000s')
    expect(sectionLabels).toContain('2010s')
  })

  it('respects the originX / originY offset', () => {
    const d = parseTimeline('timeline\n2001 : A')!
    const els = timelineToElements(d, { originX: 500, originY: 300 })
    const rect = els.find((e) => e.type === 'rect') as { x: number; y: number }
    expect(rect.x).toBeGreaterThanOrEqual(500)
  })

  it('produces deterministic output for a given input', () => {
    const a = timelineToElements(parseTimeline('timeline\n2001 : A\n2002 : B')!)
    const b = timelineToElements(parseTimeline('timeline\n2001 : A\n2002 : B')!)
    expect(JSON.stringify(a)).toBe(JSON.stringify(b))
  })

  it('handles an empty timeline gracefully', () => {
    const d = parseTimeline('timeline\n  %% no periods')!
    const els = timelineToElements(d)
    expect(els).toEqual([])
  })
})
