import { describe, expect, it } from 'vitest'

import { ganttToElements, parseGantt } from './mermaid-gantt'

describe('parseGantt', () => {
  it('returns null when the source is not a Gantt chart', () => {
    expect(parseGantt('flowchart TD\nA --> B')).toBeNull()
    expect(parseGantt('')).toBeNull()
  })

  it('parses a minimal gantt with a single absolute-date task', () => {
    const d = parseGantt(`gantt
      title Project
      dateFormat YYYY-MM-DD
      Task A : 2024-01-01, 5d`)!
    expect(d.title).toBe('Project')
    expect(d.tasks).toHaveLength(1)
    expect(d.tasks[0].label).toBe('Task A')
    expect(d.tasks[0].startDay).toBe(0)
    expect(d.tasks[0].durationDays).toBe(5)
  })

  it('captures task ids when 3 fields are present', () => {
    const d = parseGantt('gantt\nTask A : a1, 2024-01-01, 5d')!
    expect(d.tasks[0].id).toBe('a1')
  })

  it('groups tasks by section in source order', () => {
    const d = parseGantt(`gantt
      section Phase 1
      Task A : 2024-01-01, 3d
      section Phase 2
      Task B : 2024-01-04, 2d`)!
    expect(d.sections).toEqual(['Phase 1', 'Phase 2'])
    expect(d.tasks[0].section).toBe('Phase 1')
    expect(d.tasks[1].section).toBe('Phase 2')
  })

  it('resolves "after id" references', () => {
    const d = parseGantt(`gantt
      Task A : a1, 2024-01-01, 5d
      Task B : a2, after a1, 3d`)!
    // A starts day 0, runs 5 days; B starts on day 5.
    expect(d.tasks[0].startDay).toBe(0)
    expect(d.tasks[1].startDay).toBe(5)
    expect(d.tasks[1].durationDays).toBe(3)
  })

  it('chains "after" references in any source order', () => {
    const d = parseGantt(`gantt
      Task C : c, after b, 2d
      Task A : a, 2024-01-01, 3d
      Task B : b, after a, 4d`)!
    // A: 0–3 (excl); B: 3–7; C: 7–9.
    expect(d.tasks.find((t) => t.id === 'a')!.startDay).toBe(0)
    expect(d.tasks.find((t) => t.id === 'b')!.startDay).toBe(3)
    expect(d.tasks.find((t) => t.id === 'c')!.startDay).toBe(7)
  })

  it('drops tasks with unresolved "after" references', () => {
    const d = parseGantt(`gantt
      Task A : a, 2024-01-01, 3d
      Task B : after ghost, 2d`)!
    expect(d.tasks).toHaveLength(1)
    expect(d.tasks[0].id).toBe('a')
  })

  it('drops tasks with non-day durations', () => {
    const d = parseGantt(`gantt
      Task A : 2024-01-01, 3d
      Task B : 2024-01-05, 2w`)!
    expect(d.tasks).toHaveLength(1)
  })

  it('skips comments + accepts axisFormat / other config silently', () => {
    const d = parseGantt(`gantt
      %% comment
      title Project
      dateFormat YYYY-MM-DD
      axisFormat %m-%d
      excludes weekends
      Task A : 2024-01-01, 1d`)!
    expect(d.tasks).toHaveLength(1)
  })

  it('computes startDay relative to the earliest task', () => {
    // First task in source isn't necessarily the earliest — the
    // resolver should still anchor day 0 at the earliest date.
    const d = parseGantt(`gantt
      Task Late  : 2024-02-01, 1d
      Task Early : 2024-01-15, 1d`)!
    const early = d.tasks.find((t) => t.label === 'Task Early')!
    expect(early.startDay).toBe(0)
    const late = d.tasks.find((t) => t.label === 'Task Late')!
    expect(late.startDay).toBe(17) // Jan 15 → Feb 1 = 17 days
  })
})

describe('ganttToElements', () => {
  it('emits a title text + axis line + tick marks + bars', () => {
    const d = parseGantt(`gantt
      title Hello
      Task A : 2024-01-01, 3d`)!
    const els = ganttToElements(d)
    // Expect: 1 title text + 1 axis line + (1 tick + 1 tick label) for
    // day 0 + (1 tick + 1 tick label) for day 7 (totalDays = 3 so the
    // for-loop emits day 0 only) + 1 task rect + 1 task label.
    // Actually with totalDays=3 the loop emits day 0 only — let's
    // just assert the high-level shape.
    expect(els.find((e) => e.type === 'text')).toBeTruthy()
    expect(els.filter((e) => e.type === 'line').length).toBeGreaterThan(0)
    const rects = els.filter((e) => e.type === 'rect')
    expect(rects).toHaveLength(1) // one task
  })

  it('emits one rect per task in source order', () => {
    const d = parseGantt(`gantt
      Task A : 2024-01-01, 2d
      Task B : 2024-01-03, 1d`)!
    const els = ganttToElements(d)
    const rects = els.filter((e) => e.type === 'rect')
    expect(rects).toHaveLength(2)
  })

  it('respects originX / originY', () => {
    const d = parseGantt('gantt\nTask A : 2024-01-01, 1d')!
    const els = ganttToElements(d, { originX: 500, originY: 300 })
    // The earliest x should be at (or just before) originX.
    const xs = els.filter((e) => 'x' in e).map((e) => (e as { x: number }).x)
    expect(Math.min(...xs)).toBeGreaterThanOrEqual(460)
  })

  it('positions tasks horizontally proportional to startDay', () => {
    const d = parseGantt(`gantt
      Task A : 2024-01-01, 1d
      Task B : 2024-01-08, 1d`)!
    const els = ganttToElements(d)
    const rects = els.filter((e) => e.type === 'rect') as Array<{
      x: number
    }>
    // Task B is 7 days after A → bar B should be 7 * day-width to
    // the right of bar A.
    expect(rects[1].x - rects[0].x).toBe(7 * 36)
  })

  it('groups tasks under their section labels', () => {
    const d = parseGantt(`gantt
      section Phase 1
      Task A : 2024-01-01, 1d
      Task B : 2024-01-02, 1d
      section Phase 2
      Task C : 2024-01-03, 1d`)!
    const els = ganttToElements(d)
    const sectionTexts = els.filter(
      (e) =>
        e.type === 'text' &&
        ((e as unknown as { text: string }).text === 'Phase 1' ||
          (e as unknown as { text: string }).text === 'Phase 2'),
    )
    expect(sectionTexts).toHaveLength(2)
  })

  it('produces deterministic layout for a given input', () => {
    const a = ganttToElements(
      parseGantt(`gantt
        section Phase
        Task A : 2024-01-01, 1d
        Task B : 2024-01-02, 1d`)!,
    )
    const b = ganttToElements(
      parseGantt(`gantt
        section Phase
        Task A : 2024-01-01, 1d
        Task B : 2024-01-02, 1d`)!,
    )
    expect(JSON.stringify(a)).toBe(JSON.stringify(b))
  })
})
