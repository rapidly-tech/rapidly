import { afterEach, describe, expect, it, vi } from 'vitest'

import { copyElementsAsPng, isCopyAsImageSupported } from './copy-as-image'
import type { CollabElement } from './elements'

// Stand-in element shape — only the fields ``copyElementsAsPng``
// passes through to the (stubbed) exporter actually matter, so we
// build a minimal record and cast it.
const fakeEl = { id: 'a' } as unknown as CollabElement

class FakeBlob {
  type = 'image/png'
  size = 4
}

class FakeClipboardItem {
  constructor(public data: Record<string, Blob>) {}
}

describe('isCopyAsImageSupported', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('returns false when ClipboardItem is missing', () => {
    vi.stubGlobal('ClipboardItem', undefined)
    expect(isCopyAsImageSupported()).toBe(false)
  })

  it('returns false when navigator.clipboard.write is missing', () => {
    vi.stubGlobal('ClipboardItem', class {})
    vi.stubGlobal('navigator', { clipboard: {} })
    expect(isCopyAsImageSupported()).toBe(false)
  })

  it('returns true when both ClipboardItem and write exist', () => {
    vi.stubGlobal('ClipboardItem', class {})
    vi.stubGlobal('navigator', {
      clipboard: { write: () => Promise.resolve() },
    })
    expect(isCopyAsImageSupported()).toBe(true)
  })
})

describe('copyElementsAsPng', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('returns ok:false reason:empty when the element list is empty', async () => {
    const result = await copyElementsAsPng([])
    expect(result).toEqual({ ok: false, reason: 'empty' })
  })

  it('returns ok:false reason:empty when the exporter produces no blob', async () => {
    const result = await copyElementsAsPng([fakeEl], undefined, {
      exportPng: async () => null,
      clipboardWrite: async () => {},
    })
    expect(result).toEqual({ ok: false, reason: 'empty' })
  })

  it('returns ok:false reason:unsupported when ClipboardItem is missing', async () => {
    vi.stubGlobal('ClipboardItem', undefined)
    const result = await copyElementsAsPng([fakeEl], undefined, {
      exportPng: async () => new FakeBlob() as unknown as Blob,
      clipboardWrite: async () => {},
    })
    expect(result).toEqual({ ok: false, reason: 'unsupported' })
  })

  it('returns ok:false reason:denied when the clipboard write rejects', async () => {
    vi.stubGlobal('ClipboardItem', FakeClipboardItem)
    const result = await copyElementsAsPng([fakeEl], undefined, {
      exportPng: async () => new FakeBlob() as unknown as Blob,
      clipboardWrite: async () => {
        throw new Error('NotAllowed')
      },
    })
    expect(result).toEqual({ ok: false, reason: 'denied' })
  })

  it('wraps the blob in a ClipboardItem and writes it on success', async () => {
    vi.stubGlobal('ClipboardItem', FakeClipboardItem)
    const writes: ClipboardItem[][] = []
    const result = await copyElementsAsPng([fakeEl], undefined, {
      exportPng: async () => new FakeBlob() as unknown as Blob,
      clipboardWrite: async (items) => {
        writes.push(items)
      },
    })
    expect(result).toEqual({ ok: true })
    expect(writes).toHaveLength(1)
    const item = writes[0][0] as unknown as FakeClipboardItem
    expect(item.data['image/png']).toBeInstanceOf(FakeBlob)
  })

  it('passes ExportPNGOptions through to the exporter', async () => {
    let captured: unknown = null
    vi.stubGlobal('ClipboardItem', FakeClipboardItem)
    await copyElementsAsPng(
      [fakeEl],
      { padding: 32, scale: 3, background: null },
      {
        exportPng: async (els, opts) => {
          captured = opts
          return new FakeBlob() as unknown as Blob
        },
        clipboardWrite: async () => {},
      },
    )
    expect(captured).toEqual({ padding: 32, scale: 3, background: null })
  })

  it('uses the navigator.clipboard.write path when no override is given', async () => {
    const writes: ClipboardItem[][] = []
    vi.stubGlobal('ClipboardItem', FakeClipboardItem)
    vi.stubGlobal('navigator', {
      clipboard: {
        write: async (items: ClipboardItem[]) => {
          writes.push(items)
        },
      },
    })
    const result = await copyElementsAsPng([fakeEl], undefined, {
      exportPng: async () => new FakeBlob() as unknown as Blob,
    })
    expect(result.ok).toBe(true)
    expect(writes).toHaveLength(1)
  })
})
