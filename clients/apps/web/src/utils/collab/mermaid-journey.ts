/**
 * User-journey subset of Mermaid → Collab elements.
 *
 * Parses the simple Mermaid journey syntax — title + sections of
 * tasks scored 0–5 with optional actor lists — and lays it out as a
 * horizontal strip: title on top, section headers across the row
 * underneath, each task as a coloured cell beneath its section with
 * a score chip and actor list inside.
 *
 * What we handle
 * --------------
 *   ``journey``                          — header
 *   ``title My day``                     — title row
 *   ``section Morning``                  — section header
 *   ``Make coffee: 5: Me``               — task: name, score, actor list
 *   ``Read mail: 2: Me, Coworker``      — multiple actors
 *   ``Standup: 3``                       — actors optional
 *   ``%% comment`` lines                 — skipped
 *
 * Out of scope (decays to "ignored line"):
 *   - icons / class overrides
 *   - per-actor background colours
 *   - the ``showData`` flag on the header
 */

import type { CreateElementInput } from './element-store'

export interface JourneyTask {
  name: string
  /** 0..5 inclusive; values outside the range get clamped at render
   *  time. */
  score: number
  actors: string[]
  section: string
}

export interface JourneyDiagram {
  title: string
  sections: string[]
  tasks: JourneyTask[]
}

/** Parse the journey source. Returns ``null`` when the input doesn't
 *  begin with ``journey`` so the caller can fall through to the
 *  generic "unsupported kind" message. */
export function parseJourney(source: string): JourneyDiagram | null {
  const lines = source.split(/\r?\n/)
  let i = 0
  while (i < lines.length && !lines[i].trim()) i++
  const header = lines[i]?.trim() ?? ''
  if (!/^journey\b/i.test(header)) return null
  i++

  let title = ''
  const sections: string[] = []
  const tasks: JourneyTask[] = []
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

    // Task: ``Name: score [: actor, actor]`` — split on the colon
    // boundary. The name is everything before the first colon; the
    // score is the next field; an optional third field carries the
    // actor list.
    const taskMatch = /^([^:]+?)\s*:\s*(-?\d+(?:\.\d+)?)(?:\s*:\s*(.+))?$/.exec(
      line,
    )
    if (taskMatch) {
      tasks.push({
        name: taskMatch[1].trim(),
        score: Number(taskMatch[2]),
        actors:
          taskMatch[3]
            ?.split(',')
            .map((a) => a.trim())
            .filter(Boolean) ?? [],
        section: currentSection,
      })
      continue
    }
    // Unrecognised line — silently skip.
  }

  return { title, sections, tasks }
}

const TASK_WIDTH = 140
const TASK_HEIGHT = 80
const TASK_GAP_X = 12
const SECTION_GAP_X = 28
const SECTION_HEADER_HEIGHT = 28
const TITLE_HEIGHT = 28

export interface JourneyLayoutOptions {
  originX?: number
  originY?: number
}

/** Lay out the parsed journey and emit Collab element inputs. The
 *  caller passes the result to ``store.create`` per element inside
 *  one transaction (consistent with the other Mermaid renderers in
 *  this directory). */
export function journeyToElements(
  diagram: JourneyDiagram,
  options: JourneyLayoutOptions = {},
): CreateElementInput[] {
  const ox = options.originX ?? 0
  const oy = options.originY ?? 0
  const out: CreateElementInput[] = []

  // Group tasks by section in source order. Tasks with no section
  // declared land in a synthetic "" group that renders without a
  // section header.
  const groups: Array<{ section: string; tasks: JourneyTask[] }> = []
  if (diagram.sections.length === 0) {
    if (diagram.tasks.length > 0) {
      groups.push({ section: '', tasks: diagram.tasks })
    }
  } else {
    for (const section of diagram.sections) {
      groups.push({
        section,
        tasks: diagram.tasks.filter((t) => t.section === section),
      })
    }
    const orphans = diagram.tasks.filter((t) => t.section === '')
    if (orphans.length > 0) groups.push({ section: '', tasks: orphans })
  }

  // Title.
  if (diagram.title) {
    out.push({
      type: 'text',
      x: ox,
      y: oy,
      width: Math.max(TASK_WIDTH * 4, totalWidth(groups)),
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
      seed: hash('journey-title'),
      version: 0,
      locked: false,
      angle: 0,
      zIndex: 0,
      groupIds: [],
    } as CreateElementInput)
  }

  // Walk the groups left-to-right, emitting a section header and
  // then one task cell per task underneath.
  const headerY = oy + (diagram.title ? TITLE_HEIGHT : 0)
  const cellsY = headerY + SECTION_HEADER_HEIGHT
  let cursorX = ox
  for (const group of groups) {
    const groupWidth =
      group.tasks.length * TASK_WIDTH +
      Math.max(0, group.tasks.length - 1) * TASK_GAP_X
    if (group.section.length > 0) {
      out.push({
        type: 'text',
        x: cursorX,
        y: headerY,
        width: groupWidth,
        height: SECTION_HEADER_HEIGHT - 6,
        text: group.section,
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
        seed: hash('journey-section-' + group.section),
        version: 0,
        locked: false,
        angle: 0,
        zIndex: 0,
        groupIds: [],
      } as CreateElementInput)
    }
    group.tasks.forEach((task, idx) => {
      const x = cursorX + idx * (TASK_WIDTH + TASK_GAP_X)
      const y = cellsY
      const fill = scoreToFill(task.score)
      out.push({
        type: 'rect',
        x,
        y,
        width: TASK_WIDTH,
        height: TASK_HEIGHT,
        strokeColor: '#1e1e1e',
        fillColor: fill,
        fillStyle: 'solid',
        strokeWidth: 1,
        strokeStyle: 'solid',
        roughness: 0,
        opacity: 100,
        seed: hash('journey-task-' + task.name + '-' + group.section),
        version: 0,
        locked: false,
        angle: 0,
        zIndex: 0,
        groupIds: [],
        roundness: 6,
      } as CreateElementInput)
      // Task name (top of the cell).
      out.push({
        type: 'text',
        x: x + 8,
        y: y + 8,
        width: TASK_WIDTH - 16,
        height: 18,
        text: task.name,
        fontFamily: 'sans',
        fontSize: 13,
        textAlign: 'center',
        fontWeight: 'bold',
        strokeColor: '#1e1e1e',
        fillColor: 'transparent',
        fillStyle: 'none',
        strokeWidth: 1,
        strokeStyle: 'solid',
        roughness: 0,
        opacity: 100,
        seed: hash('journey-task-name-' + task.name),
        version: 0,
        locked: false,
        angle: 0,
        zIndex: 0,
        groupIds: [],
      } as CreateElementInput)
      // Score chip — small ★N row centred under the name.
      const clampedScore = Math.max(0, Math.min(5, Math.round(task.score)))
      out.push({
        type: 'text',
        x: x + 8,
        y: y + 30,
        width: TASK_WIDTH - 16,
        height: 18,
        text: `${'★'.repeat(clampedScore)}${'☆'.repeat(5 - clampedScore)}`,
        fontFamily: 'sans',
        fontSize: 14,
        textAlign: 'center',
        strokeColor: '#475569',
        fillColor: 'transparent',
        fillStyle: 'none',
        strokeWidth: 1,
        strokeStyle: 'solid',
        roughness: 0,
        opacity: 100,
        seed: hash('journey-score-' + task.name),
        version: 0,
        locked: false,
        angle: 0,
        zIndex: 0,
        groupIds: [],
      } as CreateElementInput)
      // Actors row at the bottom of the cell.
      if (task.actors.length > 0) {
        out.push({
          type: 'text',
          x: x + 8,
          y: y + TASK_HEIGHT - 22,
          width: TASK_WIDTH - 16,
          height: 16,
          text: task.actors.join(', '),
          fontFamily: 'sans',
          fontSize: 11,
          textAlign: 'center',
          strokeColor: '#475569',
          fillColor: 'transparent',
          fillStyle: 'none',
          strokeWidth: 1,
          strokeStyle: 'solid',
          roughness: 0,
          opacity: 100,
          seed: hash('journey-actors-' + task.name),
          version: 0,
          locked: false,
          angle: 0,
          zIndex: 0,
          groupIds: [],
        } as CreateElementInput)
      }
    })
    cursorX += groupWidth + SECTION_GAP_X
  }

  return out
}

/** Total horizontal width of every group + the gaps between them.
 *  Used so the title spans the full chart even when there are many
 *  tasks. */
function totalWidth(
  groups: Array<{ section: string; tasks: JourneyTask[] }>,
): number {
  let w = 0
  groups.forEach((g, i) => {
    if (i > 0) w += SECTION_GAP_X
    w +=
      g.tasks.length * TASK_WIDTH + Math.max(0, g.tasks.length - 1) * TASK_GAP_X
  })
  return w
}

/** Map a 0–5 score to a fill colour. 0 / 1 → reddish, 3 → amber, 5 →
 *  green. Score outside the range is clamped. We pick muted shades
 *  so the cells read as emotionally distinct without being
 *  harsh. */
function scoreToFill(score: number): string {
  const s = Math.max(0, Math.min(5, Math.round(score)))
  switch (s) {
    case 0:
    case 1:
      return '#ffe3e3' // soft red
    case 2:
      return '#ffd8a8' // peach
    case 3:
      return '#fff3bf' // amber
    case 4:
      return '#d3f9d8' // light green
    default:
      return '#b2f2bb' // green
  }
}

function hash(s: string): number {
  let h = 5381
  for (let i = 0; i < s.length; i++) h = (h * 33) ^ s.charCodeAt(i)
  return h >>> 0
}
