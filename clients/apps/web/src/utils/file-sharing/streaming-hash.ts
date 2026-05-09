/**
 * Incremental SHA-256 implementation for streaming file hashing.
 *
 * Web Crypto's `crypto.subtle.digest()` requires the entire input at once,
 * which causes OOM for large files. This implements FIPS 180-4 SHA-256
 * with an `update(chunk)` / `finalize()` API for incremental hashing.
 *
 * Used by uploader (hash file before sending) and downloader (verify
 * hash as chunks arrive) without holding the entire file in memory.
 */

// ── SHA-256 Constants ──

// SHA-256 constants: first 32 bits of fractional parts of cube roots of first 64 primes
const K = new Uint32Array([
  0x428a2f98, 0x71374491, 0xb5c0fbcf, 0xe9b5dba5, 0x3956c25b, 0x59f111f1,
  0x923f82a4, 0xab1c5ed5, 0xd807aa98, 0x12835b01, 0x243185be, 0x550c7dc3,
  0x72be5d74, 0x80deb1fe, 0x9bdc06a7, 0xc19bf174, 0xe49b69c1, 0xefbe4786,
  0x0fc19dc6, 0x240ca1cc, 0x2de92c6f, 0x4a7484aa, 0x5cb0a9dc, 0x76f988da,
  0x983e5152, 0xa831c66d, 0xb00327c8, 0xbf597fc7, 0xc6e00bf3, 0xd5a79147,
  0x06ca6351, 0x14292967, 0x27b70a85, 0x2e1b2138, 0x4d2c6dfc, 0x53380d13,
  0x650a7354, 0x766a0abb, 0x81c2c92e, 0x92722c85, 0xa2bfe8a1, 0xa81a664b,
  0xc24b8b70, 0xc76c51a3, 0xd192e819, 0xd6990624, 0xf40e3585, 0x106aa070,
  0x19a4c116, 0x1e376c08, 0x2748774c, 0x34b0bcb5, 0x391c0cb3, 0x4ed8aa4a,
  0x5b9cca4f, 0x682e6ff3, 0x748f82ee, 0x78a5636f, 0x84c87814, 0x8cc70208,
  0x90befffa, 0xa4506ceb, 0xbef9a3f7, 0xc67178f2,
])

// ── Bit Manipulation ──

function rotr(x: number, n: number): number {
  return (x >>> n) | (x << (32 - n))
}

// ── StreamingSHA256 ──

export class StreamingSHA256 {
  private h = new Uint32Array(8)
  private buffer = new Uint8Array(64) // 512-bit block
  private bufferOffset = 0
  private totalBytes = 0
  private finalized = false

  constructor() {
    // Initial hash values: first 32 bits of fractional parts of square roots of first 8 primes
    this.h[0] = 0x6a09e667
    this.h[1] = 0xbb67ae85
    this.h[2] = 0x3c6ef372
    this.h[3] = 0xa54ff53a
    this.h[4] = 0x510e527f
    this.h[5] = 0x9b05688c
    this.h[6] = 0x1f83d9ab
    this.h[7] = 0x5be0cd19
  }

  private processBlock(block: Uint8Array): void {
    const W = new Uint32Array(64)

    // Prepare message schedule
    for (let t = 0; t < 16; t++) {
      W[t] =
        (block[t * 4] << 24) |
        (block[t * 4 + 1] << 16) |
        (block[t * 4 + 2] << 8) |
        block[t * 4 + 3]
    }
    for (let t = 16; t < 64; t++) {
      const s0 = rotr(W[t - 15], 7) ^ rotr(W[t - 15], 18) ^ (W[t - 15] >>> 3)
      const s1 = rotr(W[t - 2], 17) ^ rotr(W[t - 2], 19) ^ (W[t - 2] >>> 10)
      W[t] = (W[t - 16] + s0 + W[t - 7] + s1) | 0
    }

    // Working variables
    let a = this.h[0]
    let b = this.h[1]
    let c = this.h[2]
    let d = this.h[3]
    let e = this.h[4]
    let f = this.h[5]
    let g = this.h[6]
    let h = this.h[7]

    // 64 rounds
    for (let t = 0; t < 64; t++) {
      const S1 = rotr(e, 6) ^ rotr(e, 11) ^ rotr(e, 25)
      const ch = (e & f) ^ (~e & g)
      const temp1 = (h + S1 + ch + K[t] + W[t]) | 0
      const S0 = rotr(a, 2) ^ rotr(a, 13) ^ rotr(a, 22)
      const maj = (a & b) ^ (a & c) ^ (b & c)
      const temp2 = (S0 + maj) | 0

      h = g
      g = f
      f = e
      e = (d + temp1) | 0
      d = c
      c = b
      b = a
      a = (temp1 + temp2) | 0
    }

    // Update hash state
    this.h[0] = (this.h[0] + a) | 0
    this.h[1] = (this.h[1] + b) | 0
    this.h[2] = (this.h[2] + c) | 0
    this.h[3] = (this.h[3] + d) | 0
    this.h[4] = (this.h[4] + e) | 0
    this.h[5] = (this.h[5] + f) | 0
    this.h[6] = (this.h[6] + g) | 0
    this.h[7] = (this.h[7] + h) | 0
  }

  /** Feed data into the hash. Can be called multiple times. */
  update(data: ArrayBuffer | Uint8Array): void {
    if (this.finalized) throw new Error('Hash already finalized')

    const bytes = data instanceof Uint8Array ? data : new Uint8Array(data)
    this.totalBytes += bytes.byteLength

    let offset = 0
    while (offset < bytes.byteLength) {
      const remaining = 64 - this.bufferOffset
      const toCopy = Math.min(remaining, bytes.byteLength - offset)
      this.buffer.set(
        bytes.subarray(offset, offset + toCopy),
        this.bufferOffset,
      )
      this.bufferOffset += toCopy
      offset += toCopy

      if (this.bufferOffset === 64) {
        this.processBlock(this.buffer)
        this.bufferOffset = 0
      }
    }
  }

  /**
   * Serialize the hasher state for persistence (e.g. IndexedDB).
   * Used by the resume feature to save hash progress between sessions.
   */
  serialize(): {
    h: number[]
    buffer: number[]
    bufferOffset: number
    totalBytes: number
  } {
    if (this.finalized) throw new Error('Cannot serialize finalized hash')
    return {
      h: Array.from(this.h),
      buffer: Array.from(this.buffer),
      bufferOffset: this.bufferOffset,
      totalBytes: this.totalBytes,
    }
  }

  /**
   * Restore a hasher from serialized state.
   * Returns a new StreamingSHA256 instance with the given state.
   */
  static deserialize(state: {
    h: number[]
    buffer: number[]
    bufferOffset: number
    totalBytes: number
  }): StreamingSHA256 {
    const hasher = new StreamingSHA256()
    hasher.h = new Uint32Array(state.h)
    hasher.buffer = new Uint8Array(state.buffer)
    hasher.bufferOffset = state.bufferOffset
    hasher.totalBytes = state.totalBytes
    return hasher
  }

  /** Finalize and return the hex digest. Can only be called once. */
  finalize(): string {
    if (this.finalized) throw new Error('Hash already finalized')
    this.finalized = true

    // Padding: append 1 bit, then zeros, then 64-bit big-endian length
    const totalBits = this.totalBytes * 8

    // Append 0x80 byte
    this.buffer[this.bufferOffset++] = 0x80

    // If not enough room for 8-byte length, pad this block and process
    if (this.bufferOffset > 56) {
      this.buffer.fill(0, this.bufferOffset)
      this.processBlock(this.buffer)
      this.bufferOffset = 0
    }

    // Pad with zeros up to length field
    this.buffer.fill(0, this.bufferOffset, 56)

    // Append 64-bit big-endian bit length
    // JavaScript numbers are 64-bit floats; totalBits = totalBytes * 8 loses
    // precision above 2^50 bytes (~1 PB). Sufficient for browser transfers.
    const highBits = Math.floor(totalBits / 0x100000000)
    const lowBits = totalBits >>> 0
    this.buffer[56] = (highBits >>> 24) & 0xff
    this.buffer[57] = (highBits >>> 16) & 0xff
    this.buffer[58] = (highBits >>> 8) & 0xff
    this.buffer[59] = highBits & 0xff
    this.buffer[60] = (lowBits >>> 24) & 0xff
    this.buffer[61] = (lowBits >>> 16) & 0xff
    this.buffer[62] = (lowBits >>> 8) & 0xff
    this.buffer[63] = lowBits & 0xff

    this.processBlock(this.buffer)

    // Convert hash state to hex string
    let hex = ''
    for (let i = 0; i < 8; i++) {
      hex += (this.h[i] >>> 0).toString(16).padStart(8, '0')
    }
    return hex
  }
}

// ── File Hashing ──

/**
 * Compute SHA-256 of a File/Blob by streaming in chunks.
 * Uses Blob.stream() when available (all modern browsers).
 * Falls back to slice-based reading for environments without stream support.
 *
 * @param file - File or Blob to hash
 * @param chunkSize - Size of each read chunk for fallback path (default 1MB)
 */
export async function computeFileSHA256Streaming(
  file: Blob,
  chunkSize = 1024 * 1024,
): Promise<string> {
  const hash = new StreamingSHA256()

  if (typeof file.stream === 'function') {
    // Preferred: use ReadableStream API (zero-copy, memory efficient)
    const reader = file.stream().getReader()
    for (;;) {
      const { done, value } = await reader.read()
      if (done) break
      hash.update(value)
    }
  } else {
    // Fallback: read via FileReader (for older environments / jsdom tests)
    for (let offset = 0; offset < file.size; offset += chunkSize) {
      const slice = file.slice(offset, Math.min(offset + chunkSize, file.size))
      const buffer = await new Promise<ArrayBuffer>((resolve, reject) => {
        const reader = new FileReader()
        reader.onload = () => resolve(reader.result as ArrayBuffer)
        reader.onerror = () => reject(reader.error)
        reader.readAsArrayBuffer(slice)
      })
      hash.update(new Uint8Array(buffer))
    }
  }

  return hash.finalize()
}
