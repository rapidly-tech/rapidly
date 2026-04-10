import { describe, expect, it } from 'vitest'
import { StreamingSHA256, computeFileSHA256Streaming } from './streaming-hash'

/**
 * Reference SHA-256 using Web Crypto for verification.
 */
async function referenceSHA256(data: Uint8Array): Promise<string> {
  const hashBuffer = await crypto.subtle.digest(
    'SHA-256',
    data.buffer as ArrayBuffer,
  )
  return Array.from(new Uint8Array(hashBuffer))
    .map((b) => b.toString(16).padStart(2, '0'))
    .join('')
}

describe('StreamingSHA256', () => {
  it('computes correct hash for empty input', () => {
    const hash = new StreamingSHA256()
    const result = hash.finalize()
    // SHA-256 of empty string is well-known (NIST test vector)
    expect(result).toBe(
      'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855',
    )
  })

  it('computes correct hash for "abc" (NIST test vector)', () => {
    const hash = new StreamingSHA256()
    hash.update(new TextEncoder().encode('abc'))
    const result = hash.finalize()
    expect(result).toBe(
      'ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad',
    )
  })

  it('computes correct hash for 448-bit message (NIST test vector)', () => {
    const hash = new StreamingSHA256()
    hash.update(
      new TextEncoder().encode(
        'abcdbcdecdefdefgefghfghighijhijkijkljklmklmnlmnomnopnopq',
      ),
    )
    const result = hash.finalize()
    expect(result).toBe(
      '248d6a61d20638b8e5c026930c3e6039a33ce45964ff2167f6ecedd419db06c1',
    )
  })

  it('matches Web Crypto digest for single update', async () => {
    const data = new Uint8Array(1000)
    crypto.getRandomValues(data)

    const hash = new StreamingSHA256()
    hash.update(data)
    const streamingResult = hash.finalize()

    const reference = await referenceSHA256(data)
    expect(streamingResult).toBe(reference)
  })

  it('matches Web Crypto digest with multiple small updates', async () => {
    const data = new Uint8Array(1000)
    crypto.getRandomValues(data)

    const hash = new StreamingSHA256()
    // Feed data in 7-byte chunks (odd size to test buffer boundary handling)
    for (let i = 0; i < data.length; i += 7) {
      hash.update(data.subarray(i, Math.min(i + 7, data.length)))
    }
    const streamingResult = hash.finalize()

    const reference = await referenceSHA256(data)
    expect(streamingResult).toBe(reference)
  })

  it('matches Web Crypto digest with chunk sizes crossing block boundaries', async () => {
    const data = new Uint8Array(256)
    crypto.getRandomValues(data)

    const hash = new StreamingSHA256()
    // Feed exactly at block boundary (64 bytes), then remainder
    hash.update(data.subarray(0, 64))
    hash.update(data.subarray(64, 128))
    hash.update(data.subarray(128, 200))
    hash.update(data.subarray(200))
    const streamingResult = hash.finalize()

    const reference = await referenceSHA256(data)
    expect(streamingResult).toBe(reference)
  })

  it('matches Web Crypto digest for exactly one block (64 bytes)', async () => {
    const data = new Uint8Array(64)
    crypto.getRandomValues(data)

    const hash = new StreamingSHA256()
    hash.update(data)
    const streamingResult = hash.finalize()

    const reference = await referenceSHA256(data)
    expect(streamingResult).toBe(reference)
  })

  it('matches Web Crypto digest for 63 bytes (one byte short of block)', async () => {
    const data = new Uint8Array(63)
    crypto.getRandomValues(data)

    const hash = new StreamingSHA256()
    hash.update(data)
    const streamingResult = hash.finalize()

    const reference = await referenceSHA256(data)
    expect(streamingResult).toBe(reference)
  })

  it('matches Web Crypto digest for 65 bytes (one byte over block)', async () => {
    const data = new Uint8Array(65)
    crypto.getRandomValues(data)

    const hash = new StreamingSHA256()
    hash.update(data)
    const streamingResult = hash.finalize()

    const reference = await referenceSHA256(data)
    expect(streamingResult).toBe(reference)
  })

  it('matches Web Crypto digest for 55 bytes (padding boundary)', async () => {
    // 55 bytes + 1 padding byte + 8 length bytes = 64 (exactly one block after padding)
    const data = new Uint8Array(55)
    crypto.getRandomValues(data)

    const hash = new StreamingSHA256()
    hash.update(data)
    const streamingResult = hash.finalize()

    const reference = await referenceSHA256(data)
    expect(streamingResult).toBe(reference)
  })

  it('matches Web Crypto digest for 56 bytes (needs extra padding block)', async () => {
    // 56 bytes + 1 padding byte = 57 > 56, so needs a second block for length
    const data = new Uint8Array(56)
    crypto.getRandomValues(data)

    const hash = new StreamingSHA256()
    hash.update(data)
    const streamingResult = hash.finalize()

    const reference = await referenceSHA256(data)
    expect(streamingResult).toBe(reference)
  })

  it('matches Web Crypto digest for large data (256KB)', async () => {
    // jsdom limits crypto.getRandomValues to 65536 bytes, so fill in chunks
    const data = new Uint8Array(256 * 1024)
    for (let i = 0; i < data.length; i += 65536) {
      crypto.getRandomValues(data.subarray(i, Math.min(i + 65536, data.length)))
    }

    const hash = new StreamingSHA256()
    // Feed in 16KB chunks (simulating file read)
    const chunkSize = 16 * 1024
    for (let i = 0; i < data.length; i += chunkSize) {
      hash.update(data.subarray(i, Math.min(i + chunkSize, data.length)))
    }
    const streamingResult = hash.finalize()

    const reference = await referenceSHA256(data)
    expect(streamingResult).toBe(reference)
  })

  it('matches Web Crypto with single-byte updates', async () => {
    const data = new TextEncoder().encode('Hello, World!')

    const hash = new StreamingSHA256()
    for (let i = 0; i < data.length; i++) {
      hash.update(data.subarray(i, i + 1))
    }
    const streamingResult = hash.finalize()

    const reference = await referenceSHA256(data)
    expect(streamingResult).toBe(reference)
  })

  it('throws if update called after finalize', () => {
    const hash = new StreamingSHA256()
    hash.finalize()
    expect(() => hash.update(new Uint8Array(1))).toThrow(
      'Hash already finalized',
    )
  })

  it('throws if finalize called twice', () => {
    const hash = new StreamingSHA256()
    hash.finalize()
    expect(() => hash.finalize()).toThrow('Hash already finalized')
  })

  it('handles ArrayBuffer input (not just Uint8Array)', async () => {
    const data = new Uint8Array(100)
    crypto.getRandomValues(data)

    const hash = new StreamingSHA256()
    hash.update(data.buffer) // Pass ArrayBuffer, not Uint8Array
    const streamingResult = hash.finalize()

    const reference = await referenceSHA256(data)
    expect(streamingResult).toBe(reference)
  })
})

describe('computeFileSHA256Streaming', () => {
  it('hashes a Blob correctly', async () => {
    const data = new Uint8Array(500)
    crypto.getRandomValues(data)
    const blob = new Blob([data])

    const streamingResult = await computeFileSHA256Streaming(blob)
    const reference = await referenceSHA256(data)
    expect(streamingResult).toBe(reference)
  })

  it('hashes an empty Blob correctly', async () => {
    const blob = new Blob([])
    const result = await computeFileSHA256Streaming(blob)
    expect(result).toBe(
      'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855',
    )
  })

  it('hashes a text Blob correctly', async () => {
    const text = 'The quick brown fox jumps over the lazy dog'
    const blob = new Blob([text])

    const result = await computeFileSHA256Streaming(blob)

    const reference = await referenceSHA256(new TextEncoder().encode(text))
    expect(result).toBe(reference)
  })

  it('hashes a multi-part Blob correctly', async () => {
    const part1 = new Uint8Array([1, 2, 3])
    const part2 = new Uint8Array([4, 5, 6])
    const blob = new Blob([part1, part2])

    const result = await computeFileSHA256Streaming(blob)

    const combined = new Uint8Array(6)
    combined.set(part1)
    combined.set(part2, 3)
    const reference = await referenceSHA256(combined)
    expect(result).toBe(reference)
  })
})
