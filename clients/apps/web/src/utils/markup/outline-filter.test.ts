import { describe, expect, it } from 'vitest'

import { filterOutline } from './outline-filter'
import type { OutlineNode } from './scene-outline'

const node = (
  id: string,
  label: string,
  children: OutlineNode[] = [],
): OutlineNode => ({
  id,
  kind: 'rect',
  label,
  hidden: false,
  locked: false,
  children,
})

const frame = (
  id: string,
  label: string,
  children: OutlineNode[] = [],
): OutlineNode => ({
  id,
  kind: 'frame',
  label,
  hidden: false,
  locked: false,
  children,
})

describe('filterOutline', () => {
  it('returns the tree unchanged for an empty query', () => {
    const tree = [node('a', 'Alpha'), node('b', 'Beta')]
    expect(filterOutline(tree, '')).toEqual(tree)
    expect(filterOutline(tree, '   ')).toEqual(tree)
  })

  it('matches a leaf by case-insensitive substring', () => {
    const tree = [node('a', 'Alpha'), node('b', 'Beta'), node('c', 'gamma')]
    expect(filterOutline(tree, 'AL')).toEqual([node('a', 'Alpha')])
  })

  it('drops leaves that do not match', () => {
    const tree = [node('a', 'Alpha'), node('b', 'Beta')]
    expect(filterOutline(tree, 'mango')).toEqual([])
  })

  it('keeps a frame that matches and shows all its children unchanged', () => {
    const tree = [
      frame('f', 'Onboarding', [node('c1', 'Step 1'), node('c2', 'Step 2')]),
    ]
    const out = filterOutline(tree, 'onboard')
    expect(out).toHaveLength(1)
    expect(out[0].id).toBe('f')
    expect(out[0].children).toHaveLength(2)
  })

  it('keeps a non-matching frame whose child matches, with only the matching child', () => {
    const tree = [
      frame('f', 'Onboarding', [node('c1', 'Step 1'), node('c2', 'Step 2')]),
    ]
    const out = filterOutline(tree, 'step 1')
    expect(out).toHaveLength(1)
    expect(out[0].id).toBe('f')
    expect(out[0].children).toEqual([node('c1', 'Step 1')])
  })

  it('drops a frame entirely when neither it nor any child matches', () => {
    const tree = [frame('f', 'Onboarding', [node('c1', 'Step 1')])]
    expect(filterOutline(tree, 'mango')).toEqual([])
  })

  it('returns a new array (does not mutate input)', () => {
    const tree = [node('a', 'Alpha')]
    const out = filterOutline(tree, '')
    expect(out).not.toBe(tree)
  })

  it('does not mutate child arrays of frame nodes', () => {
    const children = [node('c1', 'Step 1'), node('c2', 'Step 2')]
    const tree = [frame('f', 'Onboarding', children)]
    filterOutline(tree, 'step 1')
    // The original frame's children array is untouched.
    expect(children).toHaveLength(2)
  })
})
