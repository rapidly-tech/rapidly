import { describe, expect, it, vi } from 'vitest'

import {
  CHAMBER_EXPORT_SCHEMA,
  exportCanvasToPng,
  exportStrokesToJson,
  exportStrokesToSvg,
} from './chamber-export'
import type { Stroke } from './strokes'

function stroke(overrides: Partial<Stroke> = {}): Stroke {
  return {
    by: 'user-1',
    pts: [0, 0, 10, 10, 20, 20],
    hue: 180,
    w: 3,
    ...overrides,
  }
}

describe('exportStrokesToJson', () => {
  it('wraps strokes in the versioned envelope', () => {
    const out = exportStrokesToJson([stroke()], { width: 1024, height: 600 })
    expect(out.schema).toBe(CHAMBER_EXPORT_SCHEMA)
    expect(out.version).toBe(1)
    expect(out.width).toBe(1024)
    expect(out.height).toBe(600)
    expect(out.strokes).toHaveLength(1)
  })

  it('schema marker is distinct from the Phase 14 whiteboard exporter', () => {
    // Guard against accidental round-trip into the wrong importer.
    expect(CHAMBER_EXPORT_SCHEMA).not.toBe('rapidly-collab-v1')
  })

  it('clones strokes by value — later mutations do not leak', () => {
    const src = stroke()
    const out = exportStrokesToJson([src], { width: 100, height: 100 })
    src.pts.push(999, 999)
    expect(out.strokes[0].pts).not.toContain(999)
  })

  it('JSON-stringifies round-trip to the same shape', () => {
    const out = exportStrokesToJson([stroke(), stroke({ by: 'user-2' })], {
      width: 100,
      height: 100,
    })
    const round = JSON.parse(JSON.stringify(out))
    expect(round.schema).toBe(CHAMBER_EXPORT_SCHEMA)
    expect(round.strokes).toHaveLength(2)
    expect(round.strokes[1].by).toBe('user-2')
  })

  it('empty input produces a valid empty envelope', () => {
    const out = exportStrokesToJson([], { width: 1, height: 1 })
    expect(out.strokes).toEqual([])
    expect(out.schema).toBe(CHAMBER_EXPORT_SCHEMA)
  })
})

describe('exportCanvasToPng', () => {
  it('calls canvas.toBlob and resolves with the result', async () => {
    const blob = new Blob(['fake png'], { type: 'image/png' })
    const toBlob = vi.fn((cb: BlobCallback) => cb(blob))
    const fakeCanvas = { toBlob } as unknown as HTMLCanvasElement
    const out = await exportCanvasToPng(fakeCanvas)
    expect(toBlob).toHaveBeenCalled()
    expect(out).toBe(blob)
  })

  it('resolves null when canvas.toBlob returns null', async () => {
    const toBlob = vi.fn((cb: BlobCallback) => cb(null))
    const fakeCanvas = { toBlob } as unknown as HTMLCanvasElement
    const out = await exportCanvasToPng(fakeCanvas)
    expect(out).toBeNull()
  })

  it('requests image/png mime type', async () => {
    const toBlob = vi.fn((_cb: BlobCallback, _type?: string) => {
      _cb(null)
    })
    const fakeCanvas = { toBlob } as unknown as HTMLCanvasElement
    await exportCanvasToPng(fakeCanvas)
    expect(toBlob.mock.calls[0][1]).toBe('image/png')
  })
})

describe('exportStrokesToSvg', () => {
  it('produces a valid SVG root with viewBox matching the canvas', () => {
    const svg = exportStrokesToSvg([stroke()], { width: 1024, height: 600 })
    expect(svg).toMatch(/^<svg xmlns="http:\/\/www\.w3\.org\/2000\/svg"/)
    expect(svg).toContain('viewBox="0 0 1024 600"')
    expect(svg).toContain('width="1024"')
    expect(svg).toContain('height="600"')
  })

  it('emits a background rect by default', () => {
    const svg = exportStrokesToSvg([], { width: 100, height: 100 })
    expect(svg).toContain('fill="#ffffff"')
  })

  it('omits the background rect when background is null or transparent', () => {
    const svgNull = exportStrokesToSvg([], {
      width: 100,
      height: 100,
    })
    expect(svgNull).toContain('fill="#ffffff"')

    const svgOmitted = exportStrokesToSvg(
      [],
      { width: 100, height: 100 },
      { background: null },
    )
    expect(svgOmitted).not.toMatch(/<rect[^/]*fill="#ffffff"/)

    const svgTransparent = exportStrokesToSvg(
      [],
      { width: 100, height: 100 },
      { background: 'transparent' },
    )
    expect(svgTransparent).not.toMatch(/<rect[^/]*fill="#ffffff"/)
  })

  it('emits a <polyline> per multi-point stroke with hue-derived stroke colour', () => {
    const svg = exportStrokesToSvg(
      [stroke({ pts: [0, 0, 10, 10], hue: 120, w: 4 })],
      { width: 100, height: 100 },
    )
    expect(svg).toContain('<polyline')
    expect(svg).toContain('points="0,0 10,10"')
    expect(svg).toContain('stroke="hsl(120 70% 50%)"')
    expect(svg).toContain('stroke-width="4"')
    expect(svg).toContain('fill="none"')
  })

  it('emits a <circle> for single-point strokes (tap-without-drag)', () => {
    const svg = exportStrokesToSvg(
      [stroke({ pts: [50, 50], hue: 200, w: 6 })],
      {
        width: 100,
        height: 100,
      },
    )
    expect(svg).toContain('<circle')
    expect(svg).toContain('cx="50"')
    expect(svg).toContain('cy="50"')
    expect(svg).toContain('r="3"')
    expect(svg).toContain('fill="hsl(200 70% 50%)"')
  })

  it('skips zero-point strokes silently', () => {
    const svg = exportStrokesToSvg([stroke({ pts: [] })], {
      width: 100,
      height: 100,
    })
    expect(svg).not.toContain('<polyline')
    expect(svg).not.toContain('<circle')
  })

  it('coords round to 2 decimal places', () => {
    const svg = exportStrokesToSvg(
      [stroke({ pts: [1.23456, 2.34567, 3.4, 4.5] })],
      { width: 100, height: 100 },
    )
    expect(svg).toContain('points="1.23,2.35 3.4,4.5"')
  })

  it('empty scene still produces a valid document', () => {
    const svg = exportStrokesToSvg([], { width: 100, height: 100 })
    expect(svg).toContain('<svg')
    expect(svg).toContain('</svg>')
  })
})
