import { describe, expect, it } from 'vitest'

import { dimensionLabels, formatDimensions } from './dimensions-overlay'

describe('formatDimensions', () => {
  it('joins width and height with the multiplication sign', () => {
    expect(formatDimensions(120, 80)).toBe('120 × 80')
  })

  it('rounds sub-pixel values to whole numbers', () => {
    expect(formatDimensions(120.4, 80.6)).toBe('120 × 81')
  })

  it('handles zero', () => {
    expect(formatDimensions(0, 0)).toBe('0 × 0')
  })
})

describe('dimensionLabels', () => {
  const el = (id: string, x: number, y: number, w: number, h: number) => ({
    id,
    x,
    y,
    width: w,
    height: h,
  })

  it('returns no labels when nothing is selected', () => {
    const labels = dimensionLabels([el('a', 0, 0, 100, 100)], new Set(), {
      scale: 1,
      scrollX: 0,
      scrollY: 0,
    })
    expect(labels).toEqual([])
  })

  it('only labels selected elements', () => {
    const labels = dimensionLabels(
      [el('a', 0, 0, 100, 100), el('b', 200, 0, 50, 50)],
      new Set(['b']),
      { scale: 1, scrollX: 0, scrollY: 0 },
    )
    expect(labels).toHaveLength(1)
    expect(labels[0].id).toBe('b')
  })

  it('places the label below the element by the gap', () => {
    const labels = dimensionLabels(
      [el('a', 10, 20, 100, 30)],
      new Set(['a']),
      { scale: 1, scrollX: 0, scrollY: 0 },
      6,
    )
    // Bottom-left of element at (10, 50); label sits 6px below.
    expect(labels[0].screenX).toBe(10)
    expect(labels[0].screenY).toBe(56)
  })

  it('translates by viewport scroll', () => {
    const labels = dimensionLabels(
      [el('a', 100, 200, 50, 50)],
      new Set(['a']),
      { scale: 1, scrollX: 50, scrollY: 100 },
    )
    expect(labels[0].screenX).toBe(50)
    // (200 + 50 - 100) * 1 + 6 = 156
    expect(labels[0].screenY).toBe(156)
  })

  it('scales screen position by viewport zoom', () => {
    const labels = dimensionLabels(
      [el('a', 100, 100, 50, 50)],
      new Set(['a']),
      { scale: 2, scrollX: 0, scrollY: 0 },
      6,
    )
    expect(labels[0].screenX).toBe(200)
    // (100 + 50) * 2 + 6 = 306
    expect(labels[0].screenY).toBe(306)
  })

  it('formats the W × H string for each label', () => {
    const labels = dimensionLabels([el('a', 0, 0, 120, 80)], new Set(['a']), {
      scale: 1,
      scrollX: 0,
      scrollY: 0,
    })
    expect(labels[0].text).toBe('120 × 80')
  })

  it('uses the optional formatter when provided', () => {
    // Engineering-units integration: when the host wires a formatter
    // built from a BoardScale, each axis is formatted via the
    // formatter and the label reads in real-world units.
    const formatter = { format: (px: number) => `${px * 10} mm` }
    const labels = dimensionLabels(
      [el('a', 0, 0, 5, 3)],
      new Set(['a']),
      { scale: 1, scrollX: 0, scrollY: 0 },
      6,
      formatter,
    )
    expect(labels[0].text).toBe('50 mm × 30 mm')
  })
})
