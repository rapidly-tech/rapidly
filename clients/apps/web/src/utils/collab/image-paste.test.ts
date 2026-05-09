import { describe, expect, it } from 'vitest'
import * as Y from 'yjs'

import { createElementStore } from './element-store'
import {
  createImageElement,
  extractPastedImage,
  type PastedImage,
} from './image-paste'

const TINY_PNG = 'data:image/png;base64,AAAA'

function fakeClipboard(
  items: Array<{
    kind: 'file' | 'string'
    type: string
    file?: File | null
  }>,
): DataTransfer {
  const mapped = items.map(
    (it) =>
      ({
        kind: it.kind,
        type: it.type,
        getAsFile: () => it.file ?? null,
      }) as unknown as DataTransferItem,
  )
  return {
    items: Object.assign(mapped, { length: mapped.length }),
  } as unknown as DataTransfer
}

function fakeFile(mime: string, bytes = new Uint8Array([1, 2, 3])): File {
  return new File([bytes], 'paste', { type: mime })
}

describe('extractPastedImage', () => {
  it('returns null on absent clipboardData', async () => {
    expect(await extractPastedImage(null)).toBeNull()
  })

  it('returns null when no image items are present', async () => {
    const cb = fakeClipboard([{ kind: 'string', type: 'text/plain' }])
    expect(await extractPastedImage(cb)).toBeNull()
  })

  it('returns null when an image item has no file (weird clipboard)', async () => {
    const cb = fakeClipboard([{ kind: 'file', type: 'image/png', file: null }])
    expect(await extractPastedImage(cb)).toBeNull()
  })

  it('extracts the first image item and returns its dimensions', async () => {
    const cb = fakeClipboard([
      { kind: 'file', type: 'image/png', file: fakeFile('image/png') },
    ])
    const out = await extractPastedImage(cb, {
      readDataUrl: async () => TINY_PNG,
      loadImage: async () => ({ width: 100, height: 60 }),
    })
    expect(out).toEqual({
      dataUrl: TINY_PNG,
      mimeType: 'image/png',
      width: 100,
      height: 60,
    })
  })

  it('skips non-file items and picks the image after a text item', async () => {
    const cb = fakeClipboard([
      { kind: 'string', type: 'text/plain' },
      { kind: 'file', type: 'image/jpeg', file: fakeFile('image/jpeg') },
    ])
    const out = await extractPastedImage(cb, {
      readDataUrl: async () => TINY_PNG,
      loadImage: async () => ({ width: 10, height: 10 }),
    })
    expect(out?.mimeType).toBe('image/jpeg')
  })
})

describe('createImageElement', () => {
  const base: PastedImage = {
    dataUrl: TINY_PNG,
    mimeType: 'image/png',
    width: 200,
    height: 100,
  }

  it('centers the element on the requested point', () => {
    const doc = new Y.Doc()
    const store = createElementStore(doc)
    const id = createImageElement(store, base, { center: { x: 500, y: 300 } })
    const el = store.get(id)!
    expect(el.type).toBe('image')
    expect(el.x).toBe(500 - base.width / 2)
    expect(el.y).toBe(300 - base.height / 2)
    expect(el.width).toBe(base.width)
    expect(el.height).toBe(base.height)
  })

  it('carries thumbnail, mime, and natural dimensions', () => {
    const doc = new Y.Doc()
    const store = createElementStore(doc)
    const id = createImageElement(store, base, { center: { x: 0, y: 0 } })
    const el = store.get(id)! as unknown as {
      thumbnailDataUrl: string
      mimeType: string
      naturalWidth: number
      naturalHeight: number
    }
    expect(el.thumbnailDataUrl).toBe(TINY_PNG)
    expect(el.mimeType).toBe('image/png')
    expect(el.naturalWidth).toBe(200)
    expect(el.naturalHeight).toBe(100)
  })

  it('scales down oversized images while preserving aspect ratio', () => {
    const doc = new Y.Doc()
    const store = createElementStore(doc)
    const big: PastedImage = {
      dataUrl: TINY_PNG,
      mimeType: 'image/png',
      width: 4000,
      height: 2000,
    }
    const id = createImageElement(store, big, {
      center: { x: 0, y: 0 },
      maxSize: 480,
    })
    const el = store.get(id)!
    expect(el.width).toBeLessThanOrEqual(480)
    expect(el.height).toBeLessThanOrEqual(480)
    // Aspect ratio preserved (within rounding).
    const ratio = el.width / el.height
    expect(Math.abs(ratio - 2)).toBeLessThan(0.05)
  })

  it('does not scale up small images', () => {
    const doc = new Y.Doc()
    const store = createElementStore(doc)
    const small: PastedImage = {
      dataUrl: TINY_PNG,
      mimeType: 'image/png',
      width: 50,
      height: 30,
    }
    const id = createImageElement(store, small, {
      center: { x: 0, y: 0 },
      maxSize: 480,
    })
    const el = store.get(id)!
    expect(el.width).toBe(50)
    expect(el.height).toBe(30)
  })

  it('never floors tiny-but-finite images to zero', () => {
    const doc = new Y.Doc()
    const store = createElementStore(doc)
    const tiny: PastedImage = {
      dataUrl: TINY_PNG,
      mimeType: 'image/png',
      width: 5000,
      height: 1,
    }
    const id = createImageElement(store, tiny, {
      center: { x: 0, y: 0 },
      maxSize: 480,
    })
    const el = store.get(id)!
    expect(el.height).toBeGreaterThanOrEqual(1)
  })
})
