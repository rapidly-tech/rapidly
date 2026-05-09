import { describe, expect, it } from 'vitest'
import { createZipStream } from './zip-stream'

/** Collect all bytes from a ReadableStream. */
async function collectStream(
  stream: ReadableStream<Uint8Array>,
): Promise<Uint8Array> {
  const reader = stream.getReader()
  const chunks: Uint8Array[] = []
  let totalLen = 0
  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    chunks.push(value)
    totalLen += value.byteLength
  }
  const result = new Uint8Array(totalLen)
  let offset = 0
  for (const chunk of chunks) {
    result.set(chunk, offset)
    offset += chunk.byteLength
  }
  return result
}

/** Find a 4-byte signature in the archive bytes. */
function findSignature(data: Uint8Array, sig: number): number {
  const view = new DataView(data.buffer, data.byteOffset, data.byteLength)
  for (let i = 0; i <= data.byteLength - 4; i++) {
    if (view.getUint32(i, true) === sig) return i
  }
  return -1
}

describe('ZIP stream (ZIP32 small files)', () => {
  it('creates valid ZIP32 archive for small files', async () => {
    const content = new TextEncoder().encode('Hello, World!')
    const stream = createZipStream({
      start(ctrl) {
        ctrl.enqueue({
          name: 'hello.txt',
          size: content.byteLength,
          stream: () =>
            new ReadableStream({
              start(c) {
                c.enqueue(content)
                c.close()
              },
            }),
        })
        ctrl.close()
      },
    })

    const archive = await collectStream(stream)

    // Should contain local file header (PK\x03\x04)
    expect(findSignature(archive, 0x04034b50)).toBeGreaterThanOrEqual(0)
    // Should contain central directory (PK\x01\x02)
    expect(findSignature(archive, 0x02014b50)).toBeGreaterThanOrEqual(0)
    // Should contain end of central directory (PK\x05\x06)
    expect(findSignature(archive, 0x06054b50)).toBeGreaterThanOrEqual(0)
    // Should NOT contain ZIP64 EOCD (PK\x06\x06) for small files
    expect(findSignature(archive, 0x06064b50)).toBe(-1)
  })

  it('creates archive with multiple files', async () => {
    const file1 = new TextEncoder().encode('File 1 content')
    const file2 = new TextEncoder().encode('File 2 content longer')

    const stream = createZipStream({
      start(ctrl) {
        ctrl.enqueue({
          name: 'file1.txt',
          size: file1.byteLength,
          stream: () =>
            new ReadableStream({
              start(c) {
                c.enqueue(file1)
                c.close()
              },
            }),
        })
        ctrl.enqueue({
          name: 'file2.txt',
          size: file2.byteLength,
          stream: () =>
            new ReadableStream({
              start(c) {
                c.enqueue(file2)
                c.close()
              },
            }),
        })
        ctrl.close()
      },
    })

    const archive = await collectStream(stream)

    // Should have 2 local file headers
    let count = 0
    const view = new DataView(
      archive.buffer,
      archive.byteOffset,
      archive.byteLength,
    )
    for (let i = 0; i <= archive.byteLength - 4; i++) {
      if (view.getUint32(i, true) === 0x04034b50) count++
    }
    expect(count).toBe(2)
  })

  it('rejects duplicate filenames', () => {
    const content = new TextEncoder().encode('data')
    expect(() => {
      createZipStream({
        start(ctrl) {
          ctrl.enqueue({
            name: 'same.txt',
            size: content.byteLength,
            stream: () =>
              new ReadableStream({
                start(c) {
                  c.enqueue(content)
                  c.close()
                },
              }),
          })
          ctrl.enqueue({
            name: 'same.txt',
            size: content.byteLength,
            stream: () =>
              new ReadableStream({
                start(c) {
                  c.enqueue(content)
                  c.close()
                },
              }),
          })
          ctrl.close()
        },
      })
    }).toThrow('File already exists')
  })
})

describe('ZIP stream (ZIP64 large files)', () => {
  it('emits ZIP64 structures when file size >= 0xFFFFFFFE', async () => {
    // We can't create a 4GB file in tests, but we can test the
    // conditional ZIP64 logic by declaring a file size >= threshold
    // and streaming minimal data. The ZIP64 structures should be emitted
    // based on the declared size, even if actual streamed data is small.
    const smallData = new TextEncoder().encode('tiny')

    const stream = createZipStream({
      start(ctrl) {
        ctrl.enqueue({
          name: 'huge.bin',
          size: 0xfffffffe, // Just at threshold
          stream: () =>
            new ReadableStream({
              start(c) {
                c.enqueue(smallData)
                c.close()
              },
            }),
        })
        ctrl.close()
      },
    })

    const archive = await collectStream(stream)

    // Signatures are written BE via setUint32 (e.g. 0x504b0606 → bytes 50 4b 06 06)
    // findSignature reads LE, so 50 4b 06 06 → LE uint32 = 0x06064b50
    // ZIP64 EOCD record (PK\x06\x06)
    expect(findSignature(archive, 0x06064b50)).toBeGreaterThanOrEqual(0)
    // ZIP64 EOCD locator (PK\x06\x07)
    expect(findSignature(archive, 0x07064b50)).toBeGreaterThanOrEqual(0)
    // Standard EOCD (PK\x05\x06)
    expect(findSignature(archive, 0x06054b50)).toBeGreaterThanOrEqual(0)
  })

  it('does not emit ZIP64 for files below threshold', async () => {
    const data = new TextEncoder().encode('small file')
    const stream = createZipStream({
      start(ctrl) {
        ctrl.enqueue({
          name: 'small.txt',
          size: data.byteLength,
          stream: () =>
            new ReadableStream({
              start(c) {
                c.enqueue(data)
                c.close()
              },
            }),
        })
        ctrl.close()
      },
    })

    const archive = await collectStream(stream)

    // Should NOT have ZIP64 structures
    expect(findSignature(archive, 0x06064b50)).toBe(-1)
    expect(findSignature(archive, 0x07064b50)).toBe(-1)
  })
})
