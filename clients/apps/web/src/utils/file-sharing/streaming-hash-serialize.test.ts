import { describe, expect, it } from 'vitest'
import { StreamingSHA256 } from './streaming-hash'

describe('StreamingSHA256 serialize/deserialize', () => {
  it('produces correct hash after serialize + deserialize', () => {
    const data1 = new TextEncoder().encode('Hello, ')
    const data2 = new TextEncoder().encode('World!')

    // Compute hash in one pass
    const fullHasher = new StreamingSHA256()
    fullHasher.update(data1)
    fullHasher.update(data2)
    const fullHash = fullHasher.finalize()

    // Compute hash with serialize/deserialize in between
    const hasher1 = new StreamingSHA256()
    hasher1.update(data1)
    const state = hasher1.serialize()

    const hasher2 = StreamingSHA256.deserialize(state)
    hasher2.update(data2)
    const resumedHash = hasher2.finalize()

    expect(resumedHash).toBe(fullHash)
  })

  it('serialize returns correct structure', () => {
    const hasher = new StreamingSHA256()
    hasher.update(new TextEncoder().encode('test'))
    const state = hasher.serialize()

    expect(state.h).toHaveLength(8)
    expect(state.buffer).toHaveLength(64)
    expect(typeof state.bufferOffset).toBe('number')
    expect(typeof state.totalBytes).toBe('number')
    expect(state.totalBytes).toBe(4) // "test" is 4 bytes
  })

  it('throws when serializing a finalized hasher', () => {
    const hasher = new StreamingSHA256()
    hasher.update(new TextEncoder().encode('test'))
    hasher.finalize()
    expect(() => hasher.serialize()).toThrow('Cannot serialize finalized hash')
  })

  it('deserialized hasher matches empty input hash', () => {
    const fresh = new StreamingSHA256()
    const state = fresh.serialize()
    const restored = StreamingSHA256.deserialize(state)
    const hash = restored.finalize()

    expect(hash).toBe(
      'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855',
    )
  })

  it('works across block boundaries', () => {
    // SHA-256 processes 64-byte blocks. Test serialization at various offsets.
    const data = new Uint8Array(200)
    crypto.getRandomValues(data)

    // Full hash
    const fullHasher = new StreamingSHA256()
    fullHasher.update(data)
    const expected = fullHasher.finalize()

    // Split at offset 50 (mid-block), serialize, continue
    const hasher1 = new StreamingSHA256()
    hasher1.update(data.slice(0, 50))
    const state = hasher1.serialize()

    const hasher2 = StreamingSHA256.deserialize(state)
    hasher2.update(data.slice(50))
    const actual = hasher2.finalize()

    expect(actual).toBe(expected)
  })

  it('works when serialized exactly at a block boundary', () => {
    const data = new Uint8Array(128) // Exactly 2 blocks
    crypto.getRandomValues(data)

    const fullHasher = new StreamingSHA256()
    fullHasher.update(data)
    const expected = fullHasher.finalize()

    // Split at block boundary (64 bytes)
    const hasher1 = new StreamingSHA256()
    hasher1.update(data.slice(0, 64))
    const state = hasher1.serialize()

    const hasher2 = StreamingSHA256.deserialize(state)
    hasher2.update(data.slice(64))
    const actual = hasher2.finalize()

    expect(actual).toBe(expected)
  })
})
