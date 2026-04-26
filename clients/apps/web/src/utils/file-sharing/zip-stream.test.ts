import { describe, expect, it } from 'vitest'

import { ZIP64_THRESHOLD } from './constants'
import { createZipStream } from './zip-stream'

/** Stream a fixed byte string as a single-chunk ReadableStream. Mirrors
 *  the shape ``createZipStream`` expects from the ``stream()`` callback
 *  on each ``FileLike``. */
function streamOf(bytes: Uint8Array): ReadableStream<Uint8Array> {
  return new ReadableStream<Uint8Array>({
    start(ctrl) {
      ctrl.enqueue(bytes)
      ctrl.close()
    },
  })
}

async function collect(
  stream: ReadableStream<Uint8Array>,
): Promise<Uint8Array> {
  const reader = stream.getReader()
  const chunks: Uint8Array[] = []
  let total = 0
  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    chunks.push(value)
    total += value.length
  }
  const out = new Uint8Array(total)
  let offset = 0
  for (const c of chunks) {
    out.set(c, offset)
    offset += c.length
  }
  return out
}

/** Find every occurrence of a 4-byte ZIP signature in the stream. */
function findSignatures(bytes: Uint8Array, signature: number[]): number[] {
  const hits: number[] = []
  for (let i = 0; i + 4 <= bytes.length; i++) {
    if (
      bytes[i] === signature[0] &&
      bytes[i + 1] === signature[1] &&
      bytes[i + 2] === signature[2] &&
      bytes[i + 3] === signature[3]
    ) {
      hits.push(i)
    }
  }
  return hits
}

const LOCAL_FILE_HEADER = [0x50, 0x4b, 0x03, 0x04] // "PK\x03\x04"
const CENTRAL_DIR_HEADER = [0x50, 0x4b, 0x01, 0x02]
const EOCD = [0x50, 0x4b, 0x05, 0x06]
const ZIP64_EOCD = [0x50, 0x4b, 0x06, 0x06]
const ZIP64_EOCD_LOCATOR = [0x50, 0x4b, 0x06, 0x07]

describe('createZipStream — happy path', () => {
  it('produces a minimal ZIP32 archive for one small file', async () => {
    const payload = new TextEncoder().encode('hello!')
    const stream = createZipStream({
      start(ctrl) {
        ctrl.enqueue({
          name: 'hello.txt',
          size: payload.length,
          lastModified: new Date('2026-04-22T12:00:00Z').getTime(),
          stream: () => streamOf(payload),
        })
        ctrl.close()
      },
    })
    const out = await collect(stream)

    // Local file header at offset 0.
    expect(out.subarray(0, 4)).toEqual(new Uint8Array(LOCAL_FILE_HEADER))
    // Exactly one local header, one central-dir entry, one EOCD.
    expect(findSignatures(out, LOCAL_FILE_HEADER)).toHaveLength(1)
    expect(findSignatures(out, CENTRAL_DIR_HEADER)).toHaveLength(1)
    expect(findSignatures(out, EOCD)).toHaveLength(1)
    // No ZIP64 structures for a tiny file.
    expect(findSignatures(out, ZIP64_EOCD)).toHaveLength(0)
    expect(findSignatures(out, ZIP64_EOCD_LOCATOR)).toHaveLength(0)
    // Filename appears in the output.
    expect(new TextDecoder().decode(out)).toContain('hello.txt')
  })

  it('writes two local headers + two central-dir entries for two files', async () => {
    const a = new TextEncoder().encode('file-a')
    const b = new TextEncoder().encode('file-b-data')
    const stream = createZipStream({
      start(ctrl) {
        ctrl.enqueue({
          name: 'a.txt',
          size: a.length,
          stream: () => streamOf(a),
        })
        ctrl.enqueue({
          name: 'b.txt',
          size: b.length,
          stream: () => streamOf(b),
        })
        ctrl.close()
      },
    })
    const out = await collect(stream)
    expect(findSignatures(out, LOCAL_FILE_HEADER)).toHaveLength(2)
    expect(findSignatures(out, CENTRAL_DIR_HEADER)).toHaveLength(2)
    expect(findSignatures(out, EOCD)).toHaveLength(1)
    const text = new TextDecoder().decode(out)
    expect(text).toContain('a.txt')
    expect(text).toContain('b.txt')
  })

  it('produces only an EOCD for an empty archive', async () => {
    const stream = createZipStream({
      start(ctrl) {
        ctrl.close()
      },
    })
    const out = await collect(stream)
    expect(findSignatures(out, LOCAL_FILE_HEADER)).toHaveLength(0)
    expect(findSignatures(out, CENTRAL_DIR_HEADER)).toHaveLength(0)
    expect(findSignatures(out, EOCD)).toHaveLength(1)
  })

  it('appends a trailing slash to directory entries', async () => {
    const stream = createZipStream({
      start(ctrl) {
        ctrl.enqueue({ name: 'folder', directory: true })
        ctrl.close()
      },
    })
    const out = await collect(stream)
    const text = new TextDecoder().decode(out)
    expect(text).toContain('folder/')
  })
})

describe('createZipStream — ZIP64 threshold', () => {
  it('emits ZIP64 EOCD + locator when a file declares size >= ZIP64_THRESHOLD', async () => {
    // Declare a huge size but stream only a few bytes of actual data so
    // the test stays fast. The ZIP64 decision is based on declared
    // ``size``, not actual bytes streamed.
    const sentinel = new TextEncoder().encode('big')
    const stream = createZipStream({
      start(ctrl) {
        ctrl.enqueue({
          name: 'big.bin',
          size: ZIP64_THRESHOLD, // triggers ZIP64
          stream: () => streamOf(sentinel),
        })
        ctrl.close()
      },
    })
    const out = await collect(stream)
    expect(findSignatures(out, ZIP64_EOCD)).toHaveLength(1)
    expect(findSignatures(out, ZIP64_EOCD_LOCATOR)).toHaveLength(1)
    // Standard EOCD is still written (with sentinel values) alongside.
    expect(findSignatures(out, EOCD)).toHaveLength(1)
  })

  it('stays ZIP32 for files below the threshold', async () => {
    const payload = new TextEncoder().encode('small')
    const stream = createZipStream({
      start(ctrl) {
        ctrl.enqueue({
          name: 'small.bin',
          size: ZIP64_THRESHOLD - 1,
          stream: () => streamOf(payload),
        })
        ctrl.close()
      },
    })
    const out = await collect(stream)
    expect(findSignatures(out, ZIP64_EOCD)).toHaveLength(0)
    expect(findSignatures(out, ZIP64_EOCD_LOCATOR)).toHaveLength(0)
    expect(findSignatures(out, EOCD)).toHaveLength(1)
  })
})

describe('createZipStream — errors', () => {
  it('rejects a duplicate filename', async () => {
    const payload = new TextEncoder().encode('x')
    const stream = createZipStream({
      start(ctrl) {
        ctrl.enqueue({
          name: 'dup.txt',
          size: payload.length,
          stream: () => streamOf(payload),
        })
        // Second enqueue with the same name should throw synchronously
        // from the start() callback — the stream surfaces that via the
        // ReadableStream's start-rejection, which collect() then rethrows.
        expect(() =>
          ctrl.enqueue({
            name: 'dup.txt',
            size: payload.length,
            stream: () => streamOf(payload),
          }),
        ).toThrowError(/File already exists/)
        ctrl.close()
      },
    })
    // The first file still completes + archive closes cleanly.
    const out = await collect(stream)
    expect(findSignatures(out, EOCD)).toHaveLength(1)
  })

  it('rejects enqueue after close', async () => {
    const stream = createZipStream({
      start(ctrl) {
        ctrl.close()
        expect(() =>
          ctrl.enqueue({ name: 'late.txt', directory: true }),
        ).toThrowError(/closed/)
      },
    })
    await collect(stream)
  })

  it('rejects double-close', async () => {
    const stream = createZipStream({
      start(ctrl) {
        ctrl.close()
        expect(() => ctrl.close()).toThrowError(/already been requested/)
      },
    })
    await collect(stream)
  })
})
