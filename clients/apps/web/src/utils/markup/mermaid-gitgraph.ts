/**
 * gitGraph subset of Mermaid → Collab elements.
 *
 * Parses the common gitGraph syntax — commit / branch / checkout /
 * merge commands — and lays out the history as horizontal lanes
 * (one per branch) with commit circles connected by lane lines and
 * merge arrows.
 *
 * What we handle
 * --------------
 *   ``gitGraph``                       — header
 *   ``commit``                         — commit on the current branch
 *   ``commit id: "abc"``               — commit with explicit id
 *   ``commit tag: "v1"``               — commit with a tag label
 *   ``branch develop``                 — create a branch off current
 *   ``checkout develop``               — switch the current branch
 *   ``switch develop``                 — alias of checkout
 *   ``merge develop``                  — merge ``develop`` into current
 *   ``%% comment`` lines               — skipped
 *
 * Out of scope (decays to "ignored line"):
 *   - ``gitGraph LR:`` direction tweaks (always rendered LR)
 *   - ``cherry-pick`` commands
 *   - ``commit type: REVERSE / HIGHLIGHT`` flags
 */

import type { CreateElementInput } from './element-store'

export interface GitCommit {
  /** Generated id when the source didn't carry one — purely for
   *  matching merge edges back to a node. */
  id: string
  /** Optional ``tag: "..."`` label rendered above the commit. */
  tag?: string
  /** Branch the commit sits on. */
  branch: string
  /** Position along the branch lane (0..N-1 for that branch). */
  positionX: number
}

export interface GitMerge {
  /** Branch being merged in. */
  source: string
  /** Branch the merge lands on. */
  target: string
  /** X position of the resulting merge commit on the target. */
  positionX: number
}

export interface GitBranch {
  name: string
  /** Branch this one was forked from. ``null`` for the root branch. */
  forkedFrom: string | null
  /** Position on the parent branch where this fork started. */
  forkPositionX: number
  /** Lane index for layout — assigned in declaration order. */
  laneIndex: number
}

export interface GitGraph {
  branches: GitBranch[]
  commits: GitCommit[]
  merges: GitMerge[]
}

/** Parse the gitGraph source. Returns ``null`` when the input doesn't
 *  begin with ``gitGraph`` so the caller can fall through to the
 *  generic "unsupported kind" message. */
export function parseGitGraph(source: string): GitGraph | null {
  const lines = source.split(/\r?\n/)
  let i = 0
  while (i < lines.length && !lines[i].trim()) i++
  const header = lines[i]?.trim() ?? ''
  if (!/^gitGraph\b/i.test(header)) return null
  i++

  const branches: GitBranch[] = [
    { name: 'main', forkedFrom: null, forkPositionX: 0, laneIndex: 0 },
  ]
  const commits: GitCommit[] = []
  const merges: GitMerge[] = []
  // Per-branch position counters so each branch's commits stack
  // along its own lane independently. Position is the cumulative
  // x offset across the whole graph though, so a fork at commit N
  // continues from there rather than restarting.
  let globalX = 0
  let currentBranch = 'main'
  let nextAutoId = 0
  // Track the last globalX used by each branch so a checkout-and-
  // commit picks up where the branch left off.
  const branchLastX = new Map<string, number>()

  for (; i < lines.length; i++) {
    const line = lines[i].split('%%')[0].trim()
    if (line.length === 0) continue

    // ``commit`` (with optional ``id: "..."``  / ``tag: "..."`` flags).
    const commitMatch = /^commit\b(.*)$/i.exec(line)
    if (commitMatch) {
      const flags = commitMatch[1]
      const idMatch = /\bid\s*:\s*"([^"]+)"/.exec(flags)
      const tagMatch = /\btag\s*:\s*"([^"]+)"/.exec(flags)
      globalX += 1
      branchLastX.set(currentBranch, globalX)
      commits.push({
        id: idMatch?.[1] ?? `c${nextAutoId++}`,
        tag: tagMatch?.[1],
        branch: currentBranch,
        positionX: globalX,
      })
      continue
    }
    // ``branch <name>`` — create a branch off the current one.
    const branchMatch = /^branch\s+(\S+)/i.exec(line)
    if (branchMatch) {
      const name = branchMatch[1]
      if (!branches.some((b) => b.name === name)) {
        branches.push({
          name,
          forkedFrom: currentBranch,
          forkPositionX: globalX,
          laneIndex: branches.length,
        })
      }
      currentBranch = name
      branchLastX.set(name, globalX)
      continue
    }
    // ``checkout <name>`` / ``switch <name>``
    const checkoutMatch = /^(?:checkout|switch)\s+(\S+)/i.exec(line)
    if (checkoutMatch) {
      currentBranch = checkoutMatch[1]
      // Auto-create the branch if it wasn't declared explicitly —
      // matches Mermaid's lenient handling.
      if (!branches.some((b) => b.name === currentBranch)) {
        branches.push({
          name: currentBranch,
          forkedFrom: null,
          forkPositionX: 0,
          laneIndex: branches.length,
        })
      }
      continue
    }
    // ``merge <branch>``
    const mergeMatch = /^merge\s+(\S+)/i.exec(line)
    if (mergeMatch) {
      const source = mergeMatch[1]
      globalX += 1
      branchLastX.set(currentBranch, globalX)
      // The merge commit lands on the *current* branch.
      commits.push({
        id: `m${nextAutoId++}`,
        branch: currentBranch,
        positionX: globalX,
      })
      merges.push({ source, target: currentBranch, positionX: globalX })
      continue
    }
    // Unrecognised — silently skip.
  }

  return { branches, commits, merges }
}

const COMMIT_RADIUS = 12
const COMMIT_GAP_X = 60
const LANE_HEIGHT = 70
const LANE_LABEL_WIDTH = 100
const TOP_PADDING = 30

const LANE_COLOURS = [
  '#1e1e1e',
  '#1971c2',
  '#2f9e44',
  '#e03131',
  '#9c36b5',
  '#f08c00',
  '#0ca678',
  '#7048e8',
] as const

export interface GitLayoutOptions {
  originX?: number
  originY?: number
}

/** Lay the parsed graph out and emit Collab element inputs. */
export function gitGraphToElements(
  graph: GitGraph,
  options: GitLayoutOptions = {},
): CreateElementInput[] {
  const ox = options.originX ?? 0
  const oy = options.originY ?? 0
  const out: CreateElementInput[] = []

  // Each branch sits on its own lane; lane 0 is the bottom-most so
  // the main branch ends up at the bottom of the chart by default.
  // Reverse here so lane 0 is at the *top* — most users read
  // gitGraphs top-down, with main first.
  const xFor = (positionX: number): number =>
    ox + LANE_LABEL_WIDTH + (positionX - 1) * COMMIT_GAP_X
  const yFor = (lane: number): number => oy + TOP_PADDING + lane * LANE_HEIGHT
  const colourFor = (lane: number): string =>
    LANE_COLOURS[lane % LANE_COLOURS.length]

  // Map branch name → lane index so we can look up colours + Y for
  // both commits and merges.
  const laneOf = new Map<string, number>()
  for (const b of graph.branches) laneOf.set(b.name, b.laneIndex)

  // Branch labels.
  for (const b of graph.branches) {
    out.push({
      type: 'text',
      x: ox,
      y: yFor(b.laneIndex) - 9,
      width: LANE_LABEL_WIDTH - 12,
      height: 18,
      text: b.name,
      fontFamily: 'mono',
      fontSize: 13,
      textAlign: 'right',
      fontWeight: 'bold',
      strokeColor: colourFor(b.laneIndex),
      fillColor: 'transparent',
      fillStyle: 'none',
      strokeWidth: 1,
      strokeStyle: 'solid',
      roughness: 0,
      opacity: 100,
      seed: hash('git-branch-' + b.name),
      version: 0,
      locked: false,
      angle: 0,
      zIndex: 0,
      groupIds: [],
    } as CreateElementInput)
  }

  // Lane lines — connect consecutive commits on the same branch
  // with a horizontal segment so the lane reads as continuous.
  // Group commits by branch first.
  const byBranch = new Map<string, GitCommit[]>()
  for (const c of graph.commits) {
    if (!byBranch.has(c.branch)) byBranch.set(c.branch, [])
    byBranch.get(c.branch)!.push(c)
  }
  for (const [branchName, commits] of byBranch.entries()) {
    if (commits.length < 1) continue
    const lane = laneOf.get(branchName) ?? 0
    const colour = colourFor(lane)
    // Sort by positionX so the segments connect commits in order
    // even when source order interleaves multiple branches.
    commits.sort((a, b) => a.positionX - b.positionX)
    // The lane line spans from the branch's fork point (or its first
    // commit, whichever is earlier) to the last commit's x.
    const branch = graph.branches.find((b) => b.name === branchName)
    const startX =
      branch && branch.forkedFrom
        ? xFor(branch.forkPositionX + 1) - COMMIT_GAP_X / 2
        : xFor(commits[0].positionX)
    const endX = xFor(commits[commits.length - 1].positionX)
    if (endX > startX) {
      out.push({
        type: 'line',
        x: startX,
        y: yFor(lane),
        width: endX - startX,
        height: 0,
        points: [0, 0, endX - startX, 0],
        strokeColor: colour,
        fillColor: 'transparent',
        fillStyle: 'none',
        strokeWidth: 2,
        strokeStyle: 'solid',
        roughness: 0,
        opacity: 100,
        seed: hash('git-lane-' + branchName),
        version: 0,
        locked: false,
        angle: 0,
        zIndex: 0,
        groupIds: [],
      } as CreateElementInput)
    }
  }

  // Branch fork connectors — diagonal line from the parent branch's
  // commit at fork position to the new branch's lane.
  for (const b of graph.branches) {
    if (!b.forkedFrom) continue
    const parentLane = laneOf.get(b.forkedFrom) ?? 0
    const px = xFor(b.forkPositionX)
    const py = yFor(parentLane)
    const cx = xFor(b.forkPositionX + 1) - COMMIT_GAP_X / 2
    const cy = yFor(b.laneIndex)
    const minX = Math.min(px, cx)
    const minY = Math.min(py, cy)
    out.push({
      type: 'line',
      x: minX,
      y: minY,
      width: Math.abs(cx - px),
      height: Math.abs(cy - py),
      points: [px - minX, py - minY, cx - minX, cy - minY],
      strokeColor: colourFor(b.laneIndex),
      fillColor: 'transparent',
      fillStyle: 'none',
      strokeWidth: 1,
      strokeStyle: 'solid',
      roughness: 0,
      opacity: 100,
      seed: hash('git-fork-' + b.name),
      version: 0,
      locked: false,
      angle: 0,
      zIndex: 0,
      groupIds: [],
    } as CreateElementInput)
  }

  // Merge connectors — line from the source branch's last commit
  // at the merge point back into the target lane at the merge x.
  for (const m of graph.merges) {
    const sourceLane = laneOf.get(m.source) ?? 0
    const targetLane = laneOf.get(m.target) ?? 0
    const sx = xFor(m.positionX) - COMMIT_GAP_X / 2
    const sy = yFor(sourceLane)
    const tx = xFor(m.positionX)
    const ty = yFor(targetLane)
    const minX = Math.min(sx, tx)
    const minY = Math.min(sy, ty)
    out.push({
      type: 'line',
      x: minX,
      y: minY,
      width: Math.abs(tx - sx),
      height: Math.abs(ty - sy),
      points: [sx - minX, sy - minY, tx - minX, ty - minY],
      strokeColor: colourFor(sourceLane),
      fillColor: 'transparent',
      fillStyle: 'none',
      strokeWidth: 1,
      strokeStyle: 'dashed',
      roughness: 0,
      opacity: 100,
      seed: hash('git-merge-' + m.source + '-' + m.target + '-' + m.positionX),
      version: 0,
      locked: false,
      angle: 0,
      zIndex: 0,
      groupIds: [],
    } as CreateElementInput)
  }

  // Commit dots + optional tag labels.
  for (const c of graph.commits) {
    const lane = laneOf.get(c.branch) ?? 0
    const cx = xFor(c.positionX)
    const cy = yFor(lane)
    const colour = colourFor(lane)
    out.push({
      type: 'ellipse',
      x: cx - COMMIT_RADIUS,
      y: cy - COMMIT_RADIUS,
      width: COMMIT_RADIUS * 2,
      height: COMMIT_RADIUS * 2,
      strokeColor: colour,
      fillColor: colour,
      fillStyle: 'solid',
      strokeWidth: 1,
      strokeStyle: 'solid',
      roughness: 0,
      opacity: 100,
      seed: hash('git-commit-' + c.id),
      version: 0,
      locked: false,
      angle: 0,
      zIndex: 0,
      groupIds: [],
    } as CreateElementInput)
    if (c.tag) {
      out.push({
        type: 'text',
        x: cx - 30,
        y: cy - COMMIT_RADIUS - 18,
        width: 60,
        height: 14,
        text: c.tag,
        fontFamily: 'mono',
        fontSize: 11,
        textAlign: 'center',
        strokeColor: '#475569',
        fillColor: 'transparent',
        fillStyle: 'none',
        strokeWidth: 1,
        strokeStyle: 'solid',
        roughness: 0,
        opacity: 100,
        seed: hash('git-tag-' + c.id),
        version: 0,
        locked: false,
        angle: 0,
        zIndex: 0,
        groupIds: [],
      } as CreateElementInput)
    }
  }

  return out
}

function hash(s: string): number {
  let h = 5381
  for (let i = 0; i < s.length; i++) h = (h * 33) ^ s.charCodeAt(i)
  return h >>> 0
}
