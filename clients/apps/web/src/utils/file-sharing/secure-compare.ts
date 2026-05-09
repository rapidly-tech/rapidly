/**
 * Constant-time string comparison to prevent timing attacks.
 *
 * Extracted as a leaf module so both crypto.ts and encryption.ts
 * can share it without pulling in openpgp transitively.
 */
export function secureCompare(a: string, b: string): boolean {
  const encoder = new TextEncoder()
  const bufA = encoder.encode(a)
  const bufB = encoder.encode(b)

  // Fixed minimum iteration count prevents timing leaks from short inputs.
  // 64 matches SHA-256 hex length; Math.max covers longer inputs.
  const iterLength = Math.max(bufA.length, bufB.length, 64)

  // XOR all bytes - any difference will set bits in result
  let result = bufA.length ^ bufB.length
  for (let i = 0; i < iterLength; i++) {
    const byteA = i < bufA.length ? bufA[i] : 0
    const byteB = i < bufB.length ? bufB[i] : 0
    result |= byteA ^ byteB
  }

  return result === 0
}
