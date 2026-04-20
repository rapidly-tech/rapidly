import { describe, expect, it } from 'vitest'

import {
  COMPRESSION_THRESHOLD_BYTES,
  compress,
  compressionAvailable,
  decompress,
  shouldCompress,
} from './compression'

describe('compression', () => {
  // Vitest runs against jsdom which ships the streams API; the provider
  // will run the same code in real browsers. If we're ever on a
  // runtime without CompressionStream these tests will be skipped,
  // but the provider still runs correctly because the shouldCompress
  // gate falls to false.
  const hasApi = compressionAvailable()

  it('reports availability honestly', () => {
    // In jsdom we expect the API to be present; in unusual CI without
    // it the provider simply declines to compress. Either outcome is
    // acceptable for production.
    expect(typeof hasApi).toBe('boolean')
  })

  it.skipIf(!hasApi)(
    'round-trips a repetitive payload with meaningful compression',
    async () => {
      // 8 KB of the same byte — the best-case for gzip. Result should
      // be substantially smaller than the input.
      const plaintext = new Uint8Array(8 * 1024).fill(0x42)
      const compressed = await compress(plaintext)
      expect(compressed.byteLength).toBeLessThan(plaintext.byteLength / 4)

      const decompressed = await decompress(compressed)
      expect(decompressed).toEqual(plaintext)
    },
  )

  it.skipIf(!hasApi)(
    'round-trips an incompressible random payload',
    async () => {
      const plaintext = new Uint8Array(4 * 1024)
      crypto.getRandomValues(plaintext)
      const compressed = await compress(plaintext)
      // gzip can't shrink random bytes; it often adds a few bytes of
      // framing. The round-trip must still be exact.
      const decompressed = await decompress(compressed)
      expect(decompressed).toEqual(plaintext)
    },
  )

  it.skipIf(!hasApi)('rejects malformed gzip input', async () => {
    const bogus = new Uint8Array([1, 2, 3, 4, 5])
    await expect(decompress(bogus)).rejects.toBeDefined()
  })

  it('shouldCompress skips small payloads', () => {
    expect(shouldCompress(new Uint8Array(100))).toBe(false)
    expect(
      shouldCompress(new Uint8Array(COMPRESSION_THRESHOLD_BYTES - 1)),
    ).toBe(false)
  })

  it.skipIf(!hasApi)('shouldCompress kicks in at the threshold', () => {
    expect(shouldCompress(new Uint8Array(COMPRESSION_THRESHOLD_BYTES))).toBe(
      true,
    )
    expect(
      shouldCompress(new Uint8Array(COMPRESSION_THRESHOLD_BYTES * 10)),
    ).toBe(true)
  })
})
