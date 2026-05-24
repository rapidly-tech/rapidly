/**
 * Timeline subset of Mermaid → Collab elements.
 *
 * Parses the Mermaid timeline syntax — title + optional sections of
 * period rows where each row is ``period : event [: event…]`` — and
 * lays it out as a horizontal axis with period markers and event
 * cards beneath each period.
 *
 * What we handle
 * --------------
 *   ``timeline``                       — header
 *   ``title History``                  — title
 *   ``section 2000s``                  — visual grouping
 *   ``2002 : LinkedIn``                — period + one event
 *   ``2004 : Facebook : Google``       — period + multiple events
 *   ``%% comment`` lines               — skipped
 *
 * Out of scope (decays to "ignored line"):
 *   - per-section colour tuning
 *   - icons on events
 *   - markdown formatting in event labels
 */

import type { CreateElementInput } from './element-store'

export interface TimelinePeriod {
  /** Period label (a year string, a date, or any free-form text). */
  label: string
  events: string[]
  section: string
}

export interface TimelineDiagram {
  title: string
  sections: string[]
  periods: TimelinePeriod[]
}

/** Parse the timeline source. Returns ``null`` when the input doesn't
 *  begin with ``timeline`` so the caller can fall through to the
 *  generic "unsupported kind" message. */
export function parseTimeline(source: string): TimelineDiagram | null {
  const lines = source.split(/\r?\n/)
  let i = 0
  while (i < lines.length && !lines[i].trim()) i++
  const header = lines[i]?.trim() ?? ''
  if (!/^timeline\b/i.test(header)) return null
  i++

  let title = ''
  const sections: string[] = []
  const periods: TimelinePeriod[] = []
  let currentSection = ''

  for (; i < lines.length; i++) {
    const line = lines[i].split('%%')[0].trim()
    if (line.length === 0) continue

    const titleMatch = /^title\s+(.+)$/i.exec(line)
    if (titleMatch) {
      title = titleMatch[1].trim()
      continue
    }
    const sectionMatch = /^section\s+(.+)$/i.exec(line)
    if (sectionMatch) {
      currentSection = sectionMatch[1].trim()
      if (!sections.includes(currentSection)) sections.push(currentSection)
      continue
    }

    // Period row: ``label : event [: event ...]``. Split on every
    // colon — first piece is the period label, rest are events.
    if (line.includes(':')) {
      const parts = line
        .split(':')
        .map((p) => p.trim())
        .filter(Boolean)
      if (parts.length < 2) continue
      const [label, ...events] = parts
      periods.push({ label, events, section: currentSection })
      continue
    }

    // Bare period without events. Only accept when the line looks
    // like a period label (starts with a digit) so a typo or other
    // garbled non-event line doesn't get promoted to a phantom
    // period. Anything else is silently skipped.
    if (/^\d/.test(line)) {
      periods.push({ label: line, events: [], section: currentSection })
    }
  }

  return { title, sections, periods }
}

const PERIOD_GAP = 200
const TITLE_HEIGHT = 28
const SECTION_HEADER_HEIGHT = 24
const PERIOD_LABEL_HEIGHT = 28
const EVENT_HEIGHT = 28
const EVENT_GAP = 8
const TIMELINE_LINE_OFFSET = 18 // distance below period labels for the axis

export interface TimelineLayoutOptions {
  originX?: number
  originY?: number
}

/** Lay out the parsed timeline and emit Collab element inputs. */
export function timelineToElements(
  diagram: TimelineDiagram,
  options: TimelineLayoutOptions = {},
): CreateElementInput[] {
  const ox = options.originX ?? 0
  const oy = options.originY ?? 0
  const out: CreateElementInput[] = []

  if (diagram.periods.length === 0) {
    if (diagram.title) {
      out.push(makeTitle(diagram.title, ox, oy, PERIOD_GAP * 2))
    }
    return out
  }

  const totalWidth = diagram.periods.length * PERIOD_GAP
  let cursorY = oy

  // Title.
  if (diagram.title) {
    out.push(makeTitle(diagram.title, ox, cursorY, totalWidth))
    cursorY += TITLE_HEIGHT
  }

  // Section row — render section labels above the timeline if there's
  // more than one section. Each section spans the periods it owns.
  const hasSections = diagram.sections.length > 0
  if (hasSections) {
    let cursorX = ox
    for (const section of diagram.sections) {
      const periodsInSection = diagram.periods.filter(
        (p) => p.section === section,
      )
      if (periodsInSection.length === 0) continue
      const sectionWidth = periodsInSection.length * PERIOD_GAP
      out.push({
        type: 'text',
        x: cursorX,
        y: cursorY,
        width: sectionWidth,
        height: SECTION_HEADER_HEIGHT - 6,
        text: section,
        fontFamily: 'sans',
        fontSize: 14,
        textAlign: 'center',
        fontWeight: 'bold',
        strokeColor: '#1971c2',
        fillColor: 'transparent',
        fillStyle: 'none',
        strokeWidth: 1,
        strokeStyle: 'solid',
        roughness: 0,
        opacity: 100,
        seed: hash('timeline-section-' + section),
        version: 0,
        locked: false,
        angle: 0,
        zIndex: 0,
        groupIds: [],
      } as CreateElementInput)
      cursorX += sectionWidth
    }
    cursorY += SECTION_HEADER_HEIGHT
  }

  const periodLabelY = cursorY
  const axisY = periodLabelY + PERIOD_LABEL_HEIGHT + TIMELINE_LINE_OFFSET / 2
  const eventsTopY = axisY + 14

  // The horizontal axis line spans every period.
  out.push({
    type: 'line',
    x: ox + 20,
    y: axisY,
    width: totalWidth - 40,
    height: 0,
    points: [0, 0, totalWidth - 40, 0],
    strokeColor: '#475569',
    fillColor: 'transparent',
    fillStyle: 'none',
    strokeWidth: 2,
    strokeStyle: 'solid',
    roughness: 0,
    opacity: 100,
    seed: hash('timeline-axis'),
    version: 0,
    locked: false,
    angle: 0,
    zIndex: 0,
    groupIds: [],
  } as CreateElementInput)

  // Per-period rendering: label + tick mark + event cards underneath.
  diagram.periods.forEach((period, idx) => {
    const cx = ox + idx * PERIOD_GAP + PERIOD_GAP / 2
    // Period label.
    out.push({
      type: 'text',
      x: cx - PERIOD_GAP / 2 + 8,
      y: periodLabelY,
      width: PERIOD_GAP - 16,
      height: PERIOD_LABEL_HEIGHT - 6,
      text: period.label,
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
      seed: hash('timeline-period-' + period.label + '-' + idx),
      version: 0,
      locked: false,
      angle: 0,
      zIndex: 0,
      groupIds: [],
    } as CreateElementInput)
    // Tick mark — small filled circle on the axis.
    out.push({
      type: 'ellipse',
      x: cx - 5,
      y: axisY - 5,
      width: 10,
      height: 10,
      strokeColor: '#1971c2',
      fillColor: '#1971c2',
      fillStyle: 'solid',
      strokeWidth: 1,
      strokeStyle: 'solid',
      roughness: 0,
      opacity: 100,
      seed: hash('timeline-tick-' + idx),
      version: 0,
      locked: false,
      angle: 0,
      zIndex: 0,
      groupIds: [],
    } as CreateElementInput)
    // Event cards — stacked vertically under the period.
    period.events.forEach((event, ei) => {
      const ey = eventsTopY + ei * (EVENT_HEIGHT + EVENT_GAP)
      out.push({
        type: 'rect',
        x: cx - PERIOD_GAP / 2 + 8,
        y: ey,
        width: PERIOD_GAP - 16,
        height: EVENT_HEIGHT,
        strokeColor: '#1e1e1e',
        fillColor: '#a5d8ff',
        fillStyle: 'solid',
        strokeWidth: 1,
        strokeStyle: 'solid',
        roughness: 0,
        opacity: 100,
        seed: hash('timeline-event-' + period.label + '-' + ei),
        version: 0,
        locked: false,
        angle: 0,
        zIndex: 0,
        groupIds: [],
        roundness: 6,
      } as CreateElementInput)
      out.push({
        type: 'text',
        x: cx - PERIOD_GAP / 2 + 16,
        y: ey + (EVENT_HEIGHT - 16) / 2,
        width: PERIOD_GAP - 32,
        height: 16,
        text: event,
        fontFamily: 'sans',
        fontSize: 12,
        textAlign: 'center',
        strokeColor: '#1e1e1e',
        fillColor: 'transparent',
        fillStyle: 'none',
        strokeWidth: 1,
        strokeStyle: 'solid',
        roughness: 0,
        opacity: 100,
        seed: hash('timeline-event-text-' + period.label + '-' + ei),
        version: 0,
        locked: false,
        angle: 0,
        zIndex: 0,
        groupIds: [],
      } as CreateElementInput)
    })
  })

  return out
}

function makeTitle(
  text: string,
  ox: number,
  oy: number,
  width: number,
): CreateElementInput {
  return {
    type: 'text',
    x: ox,
    y: oy,
    width,
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
    seed: hash('timeline-title'),
    version: 0,
    locked: false,
    angle: 0,
    zIndex: 0,
    groupIds: [],
  } as CreateElementInput
}

function hash(s: string): number {
  let h = 5381
  for (let i = 0; i < s.length; i++) h = (h * 33) ^ s.charCodeAt(i)
  return h >>> 0
}
