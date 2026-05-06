/**
 * Component-level smoke tests for ``RadialRings``. The codebase
 * doesn't ship ``@testing-library/react`` — the unit-test layer is
 * pure data assertions — so we render via ``react-dom/server`` and
 * inspect the output HTML. Cheap and dependency-free.
 *
 * The deeper geometry / scale tests live in
 * ``utils/visualisation/radial-rings.test.ts``.
 */

import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'

import type { RingNode } from '@/utils/visualisation/radial-rings'
import { RadialRings } from './RadialRings'

const data: RingNode = {
  id: 'root',
  children: [
    { id: 'a', value: 1 },
    { id: 'b', value: 1 },
  ],
}

const countMatches = (haystack: string, needle: string): number =>
  haystack.split(needle).length - 1

describe('RadialRings (smoke)', () => {
  it('emits one path per arc (root + 2 children = 3)', () => {
    const html = renderToStaticMarkup(<RadialRings data={data} />)
    expect(countMatches(html, '<path')).toBe(3)
  })

  it('skips the root when excludeRoot is set', () => {
    const html = renderToStaticMarkup(<RadialRings data={data} excludeRoot />)
    expect(countMatches(html, '<path')).toBe(2)
  })

  it('uses a square viewBox sized to radius', () => {
    const html = renderToStaticMarkup(<RadialRings data={data} radius={150} />)
    expect(html).toContain('viewBox="-150 -150 300 300"')
  })

  it('renders labels only when showLabels is on AND the arc fits', () => {
    const html = renderToStaticMarkup(
      <RadialRings data={data} showLabels excludeRoot />,
    )
    expect(countMatches(html, '<text')).toBe(2)
  })

  it('hides labels by default', () => {
    const html = renderToStaticMarkup(<RadialRings data={data} />)
    expect(html).not.toContain('<text')
  })

  it('forwards className to the outer svg', () => {
    const html = renderToStaticMarkup(
      <RadialRings data={data} className="custom-class" />,
    )
    expect(html).toContain('class="custom-class"')
  })

  it('marks the svg aria-hidden so it stays out of the a11y tree', () => {
    const html = renderToStaticMarkup(<RadialRings data={data} />)
    expect(html).toContain('aria-hidden="true"')
  })

  it('paints each arc with the supplied colour', () => {
    const coloured: RingNode = {
      id: 'root',
      children: [
        { id: 'a', value: 1, color: '#a5d8ff' },
        { id: 'b', value: 1, color: '#b2f2bb' },
      ],
    }
    const html = renderToStaticMarkup(
      <RadialRings data={coloured} excludeRoot />,
    )
    expect(html).toContain('#a5d8ff')
    expect(html).toContain('#b2f2bb')
  })
})
