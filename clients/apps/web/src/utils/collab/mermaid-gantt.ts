/**
 * Gantt-chart subset of Mermaid → Collab elements.
 *
 * Parses the common Gantt syntax — title / date-format directives,
 * sections, and tasks with absolute or relative ("after X") start
 * dates and integer-day durations — and lays it out as a
 * timeline-on-x, section-rows-on-y chart.
 *
 * What we handle
 * --------------
 *   ``gantt``                          — header
 *   ``title My Project``               — title rendered above the chart
 *   ``dateFormat YYYY-MM-DD``          — only this format is parsed in v1
 *   ``section Phase 1``                — section row
 *   ``Task A   :id, 2024-01-01, 7d``   — task with id + abs date + duration
 *   ``Task A   :2024-01-01, 7d``       — task without id
 *   ``Task B   :id, after id1, 5d``    — task starting after another's end
 *   ``%% comment`` lines               — skipped
 *
 * Out of scope (decays harmlessly to "ignored line"):
 *   - non-day durations (``1w`` / ``2h``)
 *   - non-YYYY-MM-DD date formats
 *   - milestones (the trailing ``milestone`` flag)
 *   - critical / active / done state flags
 *   - excludes / weekends configuration
 *   - axisFormat directives beyond display
 *   - ``inclusiveEndDates`` and other config flags
 */

import type { CreateElementInput } from './element-store'

export interface GanttTask {
  /** Optional id used by ``after id`` references. */
  id?: string
  label: string
  /** Section the task belongs to — empty string when no section is
   *  declared yet. */
  section: string
  /** Days since the chart's epoch (the earliest start across all
   *  tasks). Computed in a second pass after every task is parsed
   *  so ``after`` references can resolve. */
  startDay: number
  durationDays: number
  /** Original raw start spec, kept so the resolver can backfill
   *  ``after id`` references after every task is read. */
  rawStart: string
}

export interface GanttDiagram {
  title: string
  /** ``YYYY-MM-DD`` only in v1 — recorded so a future renderer can
   *  display the date axis in the user's chosen format. */
  dateFormat: string
  /** Earliest start across all tasks. Other tasks position relative
   *  to this so the chart's leftmost task always lands at day 0. */
  epoch: Date
  sections: string[]
  tasks: GanttTask[]
}

/** Parse the Gantt source. Returns ``null`` when the input doesn't
 *  begin with ``gantt`` so the caller can fall through to the
 *  generic "unsupported kind" message. */
export function parseGantt(source: string): GanttDiagram | null {
  const lines = source.split(/\r?\n/)
  let i = 0
  while (i < lines.length && !lines[i].trim()) i++
  const header = lines[i]?.trim() ?? ''
  if (!/^gantt\b/i.test(header)) return null
  i++

  let title = ''
  let dateFormat = 'YYYY-MM-DD'
  const sections: string[] = []
  const tasks: GanttTask[] = []
  let currentSection = ''
  // Per-id lookup so the second pass can resolve ``after id``.
  const taskById = new Map<string, GanttTask>()

  for (; i < lines.length; i++) {
    const line = lines[i].split('%%')[0].trim()
    if (line.length === 0) continue

    const titleMatch = /^title\s+(.+)$/i.exec(line)
    if (titleMatch) {
      title = titleMatch[1].trim()
      continue
    }
    const dfMatch = /^dateFormat\s+(\S+)/i.exec(line)
    if (dfMatch) {
      dateFormat = dfMatch[1]
      continue
    }
    // ``axisFormat`` and other config directives — accept silently.
    if (
      /^(axisFormat|excludes|includes|todayMarker|inclusiveEndDates|topAxis|weekday)\b/i.test(
        line,
      )
    ) {
      continue
    }
    const sectionMatch = /^section\s+(.+)$/i.exec(line)
    if (sectionMatch) {
      currentSection = sectionMatch[1].trim()
      if (!sections.includes(currentSection)) sections.push(currentSection)
      continue
    }

    // Task: ``Label : [id,] start, duration``. The colon separates
    // the human label from the spec; the spec is comma-separated and
    // can have 2 or 3 fields.
    const taskMatch = /^([^:]+?)\s*:\s*(.+)$/.exec(line)
    if (!taskMatch) continue
    const label = taskMatch[1].trim()
    const spec = taskMatch[2]
      .split(',')
      .map((s) => s.trim())
      .filter(Boolean)
    if (spec.length < 2) continue
    let id: string | undefined
    let startSpec: string
    let duration: string
    if (spec.length >= 3) {
      // First field is the id when 3+ fields are present.
      id = spec[0]
      startSpec = spec[1]
      duration = spec[2]
    } else {
      // 2 fields: start + duration only.
      startSpec = spec[0]
      duration = spec[1]
    }
    const durationDays = parseDurationDays(duration)
    if (durationDays === null) continue
    const task: GanttTask = {
      id,
      label,
      section: currentSection,
      // Placeholder — resolved in the second pass.
      startDay: 0,
      durationDays,
      rawStart: startSpec,
    }
    tasks.push(task)
    if (id) taskById.set(id, task)
  }

  // Second pass: resolve every task's ``startDay``. Strategy:
  //   - For absolute YYYY-MM-DD starts, parse to a Date object.
  //   - For ``after X`` starts, find X's resolved end (start + dur)
  //     and use that.
  //   - The chart's epoch is the earliest absolute date (or the
  //     resolved start of the first task) — every other task's
  //     ``startDay`` is days since the epoch.
  // Two passes over the task list keep the resolver simple at the
  // cost of being O(N²) on chains; in practice Gantt charts here
  // are dozens of rows max so the cost is irrelevant.
  const resolved = new Map<GanttTask, Date>()
  // First, every absolute date.
  for (const t of tasks) {
    if (!/^after\b/i.test(t.rawStart)) {
      const d = parseDate(t.rawStart)
      if (d) resolved.set(t, d)
    }
  }
  // Then chase ``after`` references — repeat until no progress is
  // made, so chains of ``after`` resolve in any source order.
  let changed = true
  while (changed) {
    changed = false
    for (const t of tasks) {
      if (resolved.has(t)) continue
      const afterMatch = /^after\s+(\w+)/i.exec(t.rawStart)
      if (!afterMatch) continue
      const ref = taskById.get(afterMatch[1])
      if (!ref) continue
      const refStart = resolved.get(ref)
      if (!refStart) continue
      const end = new Date(refStart)
      end.setDate(end.getDate() + ref.durationDays)
      resolved.set(t, end)
      changed = true
    }
  }
  // Anything still unresolved is dropped so a stale ``after`` ref
  // doesn't leave a phantom task at day 0 overlapping the start.
  const finalTasks = tasks.filter((t) => resolved.has(t))
  if (finalTasks.length === 0) {
    return {
      title,
      dateFormat,
      epoch: new Date(0),
      sections,
      tasks: [],
    }
  }
  // Epoch is the earliest start across the resolved set.
  let epoch = resolved.get(finalTasks[0])!
  for (const t of finalTasks) {
    const d = resolved.get(t)!
    if (d.getTime() < epoch.getTime()) epoch = d
  }
  // Compute startDay relative to epoch.
  for (const t of finalTasks) {
    const d = resolved.get(t)!
    t.startDay = Math.round((d.getTime() - epoch.getTime()) / 86_400_000)
  }
  return {
    title,
    dateFormat,
    epoch,
    sections,
    tasks: finalTasks,
  }
}

/** Strict YYYY-MM-DD parser. Returns ``null`` for any other format
 *  (including the empty string) so the caller drops the task rather
 *  than producing a bogus epoch. */
function parseDate(s: string): Date | null {
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(s)
  if (!m) return null
  const year = Number(m[1])
  const month = Number(m[2]) - 1
  const day = Number(m[3])
  const d = new Date(Date.UTC(year, month, day))
  if (Number.isNaN(d.getTime())) return null
  return d
}

/** ``7d`` → 7. Returns ``null`` for unsupported units (``1w`` / ``2h``)
 *  so the caller can drop the task rather than mis-position it. */
function parseDurationDays(s: string): number | null {
  const m = /^(\d+)d$/i.exec(s.trim())
  if (!m) return null
  return Number(m[1])
}

const DAY_PIXEL_WIDTH = 36
const ROW_HEIGHT = 32
const ROW_GAP = 6
const SECTION_LABEL_WIDTH = 140
const TITLE_HEIGHT = 28
const AXIS_HEIGHT = 22

export interface GanttLayoutOptions {
  originX?: number
  originY?: number
}

/** Lay the parsed chart out and emit Collab element inputs. The
 *  caller passes the result to ``store.create`` per element inside
 *  one transaction (consistent with every other Mermaid renderer in
 *  this directory). */
export function ganttToElements(
  diagram: GanttDiagram,
  options: GanttLayoutOptions = {},
): CreateElementInput[] {
  const ox = options.originX ?? 0
  const oy = options.originY ?? 0
  const out: CreateElementInput[] = []

  // Rows: section header rows interleaved with their tasks. We
  // compute the row index per task by walking the section list and
  // emitting tasks in source order within each section.
  const rowOf = new Map<GanttTask, number>()
  let rowCount = 0
  if (diagram.sections.length > 0) {
    for (const section of diagram.sections) {
      for (const task of diagram.tasks.filter((t) => t.section === section)) {
        rowOf.set(task, rowCount++)
      }
    }
    // Tasks with no section land at the bottom.
    for (const task of diagram.tasks.filter((t) => t.section === '')) {
      rowOf.set(task, rowCount++)
    }
  } else {
    // No sections declared — just render tasks in source order.
    diagram.tasks.forEach((t) => rowOf.set(t, rowCount++))
  }

  // Total chart timespan (in days) = max(startDay + durationDays).
  let totalDays = 1
  for (const t of diagram.tasks) {
    const end = t.startDay + t.durationDays
    if (end > totalDays) totalDays = end
  }
  const chartWidth = totalDays * DAY_PIXEL_WIDTH

  // Title row.
  if (diagram.title) {
    out.push({
      type: 'text',
      x: ox,
      y: oy,
      width: SECTION_LABEL_WIDTH + chartWidth,
      height: TITLE_HEIGHT - 6,
      text: diagram.title,
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
      seed: hash('title'),
      version: 0,
      locked: false,
      angle: 0,
      zIndex: 0,
      groupIds: [],
    } as CreateElementInput)
  }

  // Axis: a horizontal line + day ticks at every-7-day boundary so
  // the chart reads as "weeks". Daily ticks would crowd the axis on
  // a multi-month chart.
  const axisY = oy + (diagram.title ? TITLE_HEIGHT : 0)
  out.push({
    type: 'line',
    x: ox + SECTION_LABEL_WIDTH,
    y: axisY + AXIS_HEIGHT,
    width: chartWidth,
    height: 0,
    points: [0, 0, chartWidth, 0],
    strokeColor: '#475569',
    fillColor: 'transparent',
    fillStyle: 'none',
    strokeWidth: 1,
    strokeStyle: 'solid',
    roughness: 0,
    opacity: 100,
    seed: hash('axis'),
    version: 0,
    locked: false,
    angle: 0,
    zIndex: 0,
    groupIds: [],
  } as CreateElementInput)
  // Week markers + date labels.
  for (let day = 0; day <= totalDays; day += 7) {
    const x = ox + SECTION_LABEL_WIDTH + day * DAY_PIXEL_WIDTH
    out.push({
      type: 'line',
      x,
      y: axisY + AXIS_HEIGHT - 4,
      width: 0,
      height: 4,
      points: [0, 0, 0, 4],
      strokeColor: '#475569',
      fillColor: 'transparent',
      fillStyle: 'none',
      strokeWidth: 1,
      strokeStyle: 'solid',
      roughness: 0,
      opacity: 100,
      seed: hash(`tick-${day}`),
      version: 0,
      locked: false,
      angle: 0,
      zIndex: 0,
      groupIds: [],
    } as CreateElementInput)
    const tickDate = new Date(diagram.epoch)
    tickDate.setUTCDate(tickDate.getUTCDate() + day)
    const label = tickDate.toISOString().slice(0, 10)
    out.push({
      type: 'text',
      x: x - 40,
      y: axisY,
      width: 80,
      height: 14,
      text: label,
      fontFamily: 'mono',
      fontSize: 10,
      textAlign: 'center',
      strokeColor: '#475569',
      fillColor: 'transparent',
      fillStyle: 'none',
      strokeWidth: 1,
      strokeStyle: 'solid',
      roughness: 0,
      opacity: 100,
      seed: hash(`tickLabel-${day}`),
      version: 0,
      locked: false,
      angle: 0,
      zIndex: 0,
      groupIds: [],
    } as CreateElementInput)
  }

  // Section labels — left of the timeline, one per section.
  const rowsBaseY = axisY + AXIS_HEIGHT + ROW_GAP
  if (diagram.sections.length > 0) {
    let cursor = 0
    for (const section of diagram.sections) {
      const tasksInSection = diagram.tasks.filter((t) => t.section === section)
      if (tasksInSection.length === 0) continue
      // Label sits at the vertical centre of the section's task rows.
      const startRow = cursor
      const endRow = cursor + tasksInSection.length - 1
      const cy =
        rowsBaseY +
        ((startRow + endRow) / 2) * (ROW_HEIGHT + ROW_GAP) +
        ROW_HEIGHT / 2
      out.push({
        type: 'text',
        x: ox,
        y: cy - 9,
        width: SECTION_LABEL_WIDTH - 8,
        height: 18,
        text: section,
        fontFamily: 'sans',
        fontSize: 13,
        textAlign: 'right',
        fontWeight: 'bold',
        strokeColor: '#1e1e1e',
        fillColor: 'transparent',
        fillStyle: 'none',
        strokeWidth: 1,
        strokeStyle: 'solid',
        roughness: 0,
        opacity: 100,
        seed: hash('section-' + section),
        version: 0,
        locked: false,
        angle: 0,
        zIndex: 0,
        groupIds: [],
      } as CreateElementInput)
      cursor += tasksInSection.length
    }
  }

  // Task bars + labels.
  for (const task of diagram.tasks) {
    const row = rowOf.get(task) ?? 0
    const x = ox + SECTION_LABEL_WIDTH + task.startDay * DAY_PIXEL_WIDTH
    const y = rowsBaseY + row * (ROW_HEIGHT + ROW_GAP)
    const w = Math.max(8, task.durationDays * DAY_PIXEL_WIDTH)
    out.push({
      type: 'rect',
      x,
      y,
      width: w,
      height: ROW_HEIGHT,
      strokeColor: '#1e1e1e',
      fillColor: '#a5d8ff',
      fillStyle: 'solid',
      strokeWidth: 1,
      strokeStyle: 'solid',
      roughness: 0,
      opacity: 100,
      seed: hash('task-' + (task.id ?? task.label)),
      version: 0,
      locked: false,
      angle: 0,
      zIndex: 0,
      groupIds: [],
      roundness: 4,
    } as CreateElementInput)
    out.push({
      type: 'text',
      x: x + 6,
      y: y + (ROW_HEIGHT - 16) / 2,
      width: Math.max(20, w - 12),
      height: 16,
      text: task.label,
      fontFamily: 'sans',
      fontSize: 12,
      textAlign: 'left',
      strokeColor: '#1e1e1e',
      fillColor: 'transparent',
      fillStyle: 'none',
      strokeWidth: 1,
      strokeStyle: 'solid',
      roughness: 0,
      opacity: 100,
      seed: hash('taskLabel-' + (task.id ?? task.label)),
      version: 0,
      locked: false,
      angle: 0,
      zIndex: 0,
      groupIds: [],
    } as CreateElementInput)
  }

  return out
}

function hash(s: string): number {
  let h = 5381
  for (let i = 0; i < s.length; i++) h = (h * 33) ^ s.charCodeAt(i)
  return h >>> 0
}
