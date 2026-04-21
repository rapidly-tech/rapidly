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

  it('renders a rect with rounded corners when roundness > 0', () => {
    const doc = new Y.Doc()
    const store = createElementStore(doc)
    rect(store, { roundness: 8 })
    const svg = exportToSVG(store.list())
    expect(svg).toContain('rx="8"')
    expect(svg).toContain('ry="8"')
  })

  it('serialises an ellipse with its radii', () => {
    const doc = new Y.Doc()
    const store = createElementStore(doc)
    store.create({
      type: 'ellipse',
      x: 0,
      y: 0,
      width: 100,
      height: 50,
    })
    const svg = exportToSVG(store.list())
    expect(svg).toContain('<ellipse')
    expect(svg).toContain('rx="50"')
    expect(svg).toContain('ry="25"')
  })

  it('serialises a diamond as a polygon with 4 points', () => {
    const doc = new Y.Doc()
    const store = createElementStore(doc)
    store.create({
      type: 'diamond',
      x: 0,
      y: 0,
      width: 100,
      height: 50,
      roundness: 0,
    })
    const svg = exportToSVG(store.list())
    expect(svg).toContain('<polygon')
    expect(svg).toContain('points="50,0 100,25 50,50 0,25"')
  })

  it('serialises an arrow with a marker-end reference', () => {
    const doc = new Y.Doc()
    const store = createElementStore(doc)
    store.create({
      type: 'arrow',
      x: 0,
      y: 0,
      width: 100,
      height: 0,
      points: [0, 0, 100, 0],
    })
    const svg = exportToSVG(store.list())
    expect(svg).toContain('<polyline')
    expect(svg).toContain('marker-end="url(#collab-arrow-head)"')
    expect(svg).toContain('<marker id="collab-arrow-head"')
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
