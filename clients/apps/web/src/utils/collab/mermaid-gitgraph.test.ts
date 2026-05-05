import { describe, expect, it } from 'vitest'

import { gitGraphToElements, parseGitGraph } from './mermaid-gitgraph'

describe('parseGitGraph', () => {
  it('returns null when the source is not a gitGraph', () => {
    expect(parseGitGraph('flowchart TD\nA --> B')).toBeNull()
    expect(parseGitGraph('')).toBeNull()
  })

  it('seeds main as the default branch', () => {
    const g = parseGitGraph('gitGraph\ncommit')!
    expect(g.branches.map((b) => b.name)).toEqual(['main'])
    expect(g.commits[0].branch).toBe('main')
  })

  it('captures explicit commit ids and tag flags', () => {
    const g = parseGitGraph(`gitGraph
      commit id: "first"
      commit tag: "v1"`)!
    expect(g.commits[0].id).toBe('first')
    expect(g.commits[1].tag).toBe('v1')
  })

  it('creates a branch and switches to it', () => {
    const g = parseGitGraph(`gitGraph
      commit
      branch develop
      commit`)!
    expect(g.branches.map((b) => b.name)).toEqual(['main', 'develop'])
    const dev = g.branches.find((b) => b.name === 'develop')!
    expect(dev.forkedFrom).toBe('main')
    expect(dev.forkPositionX).toBe(1)
    expect(g.commits[1].branch).toBe('develop')
  })

  it('honours checkout / switch to flip branches', () => {
    const g = parseGitGraph(`gitGraph
      commit
      branch dev
      commit
      checkout main
      commit`)!
    expect(g.commits[0].branch).toBe('main')
    expect(g.commits[1].branch).toBe('dev')
    expect(g.commits[2].branch).toBe('main')
  })

  it('records merge commits + edges', () => {
    const g = parseGitGraph(`gitGraph
      commit
      branch dev
      commit
      checkout main
      merge dev`)!
    expect(g.merges).toHaveLength(1)
    expect(g.merges[0].source).toBe('dev')
    expect(g.merges[0].target).toBe('main')
    // The merge also produces a commit on the target branch.
    const lastCommit = g.commits[g.commits.length - 1]
    expect(lastCommit.branch).toBe('main')
  })

  it('skips comments + tolerates trailing comments', () => {
    const g = parseGitGraph(`gitGraph
      %% intro
      commit %% trailing
      commit`)!
    expect(g.commits).toHaveLength(2)
  })

  it('ignores garbled lines without aborting', () => {
    const g = parseGitGraph(`gitGraph
      commit
      garbled+++
      commit`)!
    expect(g.commits).toHaveLength(2)
  })

  it('auto-creates a branch on checkout if not declared first', () => {
    const g = parseGitGraph(`gitGraph
      commit
      checkout feature
      commit`)!
    expect(g.branches.map((b) => b.name).sort()).toEqual(['feature', 'main'])
  })
})

describe('gitGraphToElements', () => {
  it('renders one ellipse per commit', () => {
    const g = parseGitGraph(`gitGraph
      commit
      commit
      commit`)!
    const els = gitGraphToElements(g)
    expect(els.filter((e) => e.type === 'ellipse')).toHaveLength(3)
  })

  it('emits a branch label per branch', () => {
    const g = parseGitGraph(`gitGraph
      commit
      branch dev
      commit`)!
    const els = gitGraphToElements(g)
    const labels = els
      .filter((e) => e.type === 'text')
      .map((e) => (e as unknown as { text: string }).text)
    expect(labels).toContain('main')
    expect(labels).toContain('dev')
  })

  it('emits a dashed line for merge edges', () => {
    const g = parseGitGraph(`gitGraph
      commit
      branch dev
      commit
      checkout main
      merge dev`)!
    const els = gitGraphToElements(g)
    const dashedLines = els.filter(
      (e) => e.type === 'line' && e.strokeStyle === 'dashed',
    )
    expect(dashedLines.length).toBeGreaterThanOrEqual(1)
  })

  it('places branches on different y lanes', () => {
    const g = parseGitGraph(`gitGraph
      commit
      branch dev
      commit`)!
    const els = gitGraphToElements(g)
    const ellipses = els.filter((e) => e.type === 'ellipse') as Array<{
      y: number
    }>
    expect(ellipses).toHaveLength(2)
    expect(ellipses[1].y).not.toBe(ellipses[0].y)
  })

  it('renders tag labels above their commits', () => {
    const g = parseGitGraph(`gitGraph
      commit tag: "v1"`)!
    const els = gitGraphToElements(g)
    const tagText = els.find(
      (e) =>
        e.type === 'text' && (e as unknown as { text: string }).text === 'v1',
    )
    expect(tagText).toBeTruthy()
  })

  it('respects the originX / originY offset', () => {
    const g = parseGitGraph('gitGraph\ncommit')!
    const els = gitGraphToElements(g, { originX: 500, originY: 300 })
    const ellipse = els.find((e) => e.type === 'ellipse') as { x: number }
    expect(ellipse.x).toBeGreaterThanOrEqual(500)
  })

  it('produces deterministic output for a given input', () => {
    const a = gitGraphToElements(
      parseGitGraph(
        `gitGraph\ncommit\nbranch d\ncommit\ncheckout main\nmerge d`,
      )!,
    )
    const b = gitGraphToElements(
      parseGitGraph(
        `gitGraph\ncommit\nbranch d\ncommit\ncheckout main\nmerge d`,
      )!,
    )
    expect(JSON.stringify(a)).toBe(JSON.stringify(b))
  })
})
