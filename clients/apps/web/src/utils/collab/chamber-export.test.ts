import { describe, expect, it, vi } from 'vitest'

import {
  CHAMBER_EXPORT_SCHEMA,
  exportCanvasToPng,
  exportStrokesToJson,
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
