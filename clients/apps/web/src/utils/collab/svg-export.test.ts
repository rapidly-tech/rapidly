import { describe, expect, it } from 'vitest'
import * as Y from 'yjs'

import { createElementStore, type ElementStore } from './element-store'
import { escapeXml, exportToSVG } from './svg-export'

function rect(
  store: ElementStore,
  overrides: Record<string, unknown> = {},
): string {
  return store.create({
    type: 'rect',
    x: 0,
    y: 0,
    width: 10,
    height: 10,
    roundness: 0,
    ...overrides,
  })
}

describe('exportToSVG', () => {
  it('produces a valid SVG root with viewBox covering the scene + padding', () => {
    const doc = new Y.Doc()
    const store = createElementStore(doc)
    rect(store, { x: 0, y: 0, width: 100, height: 50 })
    const svg = exportToSVG(store.list(), { padding: 20 })
    expect(svg).toMatch(/^<svg xmlns="http:\/\/www\.w3\.org\/2000\/svg"/)
    expect(svg).toContain('viewBox="-20 -20 140 90"')
    expect(svg).toContain('width="140"')
    expect(svg).toContain('height="90"')
  })

  it('returns a zero-sized document for an empty scene', () => {
    const svg = exportToSVG([])
    expect(svg).toContain('<svg')
    expect(svg).toContain('viewBox="0 0 1 1"')
  })

  it('emits a background rect by default', () => {
    const doc = new Y.Doc()
    const store = createElementStore(doc)
    rect(store)
    const svg = exportToSVG(store.list())
    expect(svg).toContain('fill="#ffffff"')
  })

  it('omits the background rect when background is null or transparent', () => {
    const doc = new Y.Doc()
    const store = createElementStore(doc)
    rect(store)
    const svgNull = exportToSVG(store.list(), { background: null })
    expect(svgNull.match(/<rect[^/]*fill="#ffffff"/g)).toBeNull()
    const svgTransparent = exportToSVG(store.list(), {
      background: 'transparent',
    })
    expect(svgTransparent.match(/<rect[^/]*fill="#ffffff"/g)).toBeNull()
  })

  it('renders a clean rect with rounded corners when roundness > 0 and roughness is 0', () => {
    const doc = new Y.Doc()
    const store = createElementStore(doc)
    rect(store, { roundness: 8, roughness: 0 })
    const svg = exportToSVG(store.list())
    expect(svg).toContain('rx="8"')
    expect(svg).toContain('ry="8"')
  })

  it('serialises a clean ellipse with its radii at roughness 0', () => {
    const doc = new Y.Doc()
    const store = createElementStore(doc)
    store.create({
      type: 'ellipse',
      x: 0,
      y: 0,
      width: 100,
      height: 50,
      roughness: 0,
    })
    const svg = exportToSVG(store.list())
    expect(svg).toContain('<ellipse')
    expect(svg).toContain('rx="50"')
    expect(svg).toContain('ry="25"')
  })

  it('serialises a clean diamond as a polygon at roughness 0', () => {
    const doc = new Y.Doc()
    const store = createElementStore(doc)
    store.create({
      type: 'diamond',
      x: 0,
      y: 0,
      width: 100,
      height: 50,
      roundness: 0,
      roughness: 0,
    })
    const svg = exportToSVG(store.list())
    expect(svg).toContain('<polygon')
    expect(svg).toContain('points="50,0 100,25 50,50 0,25"')
  })

  it('serialises a clean arrow as a polyline at roughness 0', () => {
    const doc = new Y.Doc()
    const store = createElementStore(doc)
    store.create({
      type: 'arrow',
      x: 0,
      y: 0,
      width: 100,
      height: 0,
      points: [0, 0, 100, 0],
      roughness: 0,
    })
    const svg = exportToSVG(store.list())
    expect(svg).toContain('<polyline')
    expect(svg).toContain('marker-end="url(#collab-arrow-head)"')
    expect(svg).toContain('<marker id="collab-arrow-head"')
  })

  it('emits a rough <path> for rect when roughness > 0', () => {
    const doc = new Y.Doc()
    const store = createElementStore(doc)
    rect(store, { roughness: 1, seed: 42 })
    const svg = exportToSVG(store.list())
    expect(svg).toContain('<path d="M')
    expect(svg).toContain('fill-rule="evenodd"')
    // No clean <rect width=...> element should appear for the rough
    // shape (the background fill still uses <rect>, so just assert
    // no per-element rect sneaks through).
    expect(svg).not.toMatch(/<rect width="10"/)
  })

  it('emits a rough <path> for ellipse + diamond + arrow at roughness > 0', () => {
    const doc = new Y.Doc()
    const store = createElementStore(doc)
    store.create({
      type: 'ellipse',
      x: 0,
      y: 0,
      width: 100,
      height: 50,
      roughness: 1,
      seed: 7,
    })
    store.create({
      type: 'diamond',
      x: 200,
      y: 0,
      width: 100,
      height: 50,
      roundness: 0,
      roughness: 2,
      seed: 8,
    })
    store.create({
      type: 'arrow',
      x: 0,
      y: 200,
      width: 100,
      height: 0,
      points: [0, 0, 100, 0],
      roughness: 1,
      seed: 9,
    })
    const svg = exportToSVG(store.list())
    expect(svg).not.toContain('<ellipse')
    expect(svg).not.toContain('<polygon')
    // Exactly one marker def + three rough paths (at minimum).
    const pathMatches = svg.match(/<path d="/g) ?? []
    expect(pathMatches.length).toBeGreaterThanOrEqual(4) // 1 marker + 3 shapes
  })

  it('rough output is seed-stable — same seed produces identical path', () => {
    const doc1 = new Y.Doc()
    const store1 = createElementStore(doc1)
    store1.create({
      type: 'ellipse',
      x: 0,
      y: 0,
      width: 100,
      height: 50,
      roughness: 2,
      seed: 12345,
    })
    const doc2 = new Y.Doc()
    const store2 = createElementStore(doc2)
    store2.create({
      type: 'ellipse',
      x: 0,
      y: 0,
      width: 100,
      height: 50,
      roughness: 2,
      seed: 12345,
    })
    expect(exportToSVG(store1.list())).toBe(exportToSVG(store2.list()))
  })

  it('applies a transform with rotation for rotated elements', () => {
    const doc = new Y.Doc()
    const store = createElementStore(doc)
    rect(store, { angle: Math.PI / 2, width: 20, height: 10 })
    const svg = exportToSVG(store.list())
    expect(svg).toMatch(/transform="translate\([^)]+\) rotate\(90 10 5\)"/)
  })

  it('escapes user text in text elements so </svg> cannot truncate the file', () => {
    const doc = new Y.Doc()
    const store = createElementStore(doc)
    store.create({
      type: 'text',
      x: 0,
      y: 0,
      width: 100,
      height: 24,
      text: '</svg><script>alert(1)</script>',
      fontFamily: 'sans',
      fontSize: 16,
      textAlign: 'left',
    })
    const svg = exportToSVG(store.list())
    expect(svg).not.toContain('</svg><script>')
    expect(svg).toContain('&lt;/svg&gt;&lt;script&gt;alert(1)&lt;/script&gt;')
  })

  it('carries opacity when the element is partly transparent', () => {
    const doc = new Y.Doc()
    const store = createElementStore(doc)
    rect(store, { opacity: 50 })
    const svg = exportToSVG(store.list())
    expect(svg).toContain('opacity="0.5"')
  })

  it('omits opacity attribute when the element is fully opaque', () => {
    const doc = new Y.Doc()
    const store = createElementStore(doc)
    rect(store, { opacity: 100 })
    const svg = exportToSVG(store.list())
    expect(svg).not.toMatch(/opacity="1"/)
  })

  it('embeds the image thumbnail via <image href>', () => {
    const doc = new Y.Doc()
    const store = createElementStore(doc)
    store.create({
      type: 'image',
      x: 0,
      y: 0,
      width: 50,
      height: 50,
      thumbnailDataUrl: 'data:image/png;base64,ABC',
      mimeType: 'image/png',
      naturalWidth: 100,
      naturalHeight: 100,
    })
    const svg = exportToSVG(store.list())
    expect(svg).toContain('<image')
    expect(svg).toContain('href="data:image/png;base64,ABC"')
  })
})

describe('escapeXml', () => {
  it('replaces the five sensitive characters', () => {
    expect(escapeXml('<a href="x" foo=\'bar\'>&</a>')).toBe(
      '&lt;a href=&quot;x&quot; foo=&apos;bar&apos;&gt;&amp;&lt;/a&gt;',
    )
  })

  it('passes plain strings through', () => {
    expect(escapeXml('hello world')).toBe('hello world')
  })
})
