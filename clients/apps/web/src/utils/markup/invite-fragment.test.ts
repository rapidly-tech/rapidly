import { describe, expect, it } from 'vitest'

import { decryptGcm, encryptGcm } from '@/utils/crypto/aes-gcm'

import {
  decodeInviteFragment,
  encodeInviteFragment,
  generateFragmentKeys,
} from './invite-fragment'

describe('invite fragment round-trip', () => {
  it('host generate → encode → decode yields a usable key on the other side', async () => {
    const hostKeys = await generateFragmentKeys()
    const fragment = await encodeInviteFragment(hostKeys)
    // Looks like URL fragment params.
    expect(fragment).toMatch(/^k=[\w-]+&s=[\w-]+$/)

    const guestKeys = await decodeInviteFragment(fragment)
    expect(guestKeys).not.toBeNull()

    // Ciphertext from the host decrypts on the guest — proves the
    // fragment carried both master and salt faithfully.
    const plaintext = new TextEncoder().encode('secret-text')
    const ct = await encryptGcm(hostKeys.masterKey, plaintext)
    const pt = await decryptGcm(guestKeys!.masterKey, ct)
    expect(new TextDecoder().decode(pt)).toBe('secret-text')
    expect(guestKeys!.salt).toEqual(hostKeys.salt)
  })

  it('accepts a leading # prefix (what window.location.hash returns)', async () => {
    const hostKeys = await generateFragmentKeys()
    const fragment = '#' + (await encodeInviteFragment(hostKeys))
    const guestKeys = await decodeInviteFragment(fragment)
    expect(guestKeys).not.toBeNull()
  })
})

describe('invite fragment — invalid / absent inputs', () => {
  it.each([null, undefined, '', '#', 'no-equals'])(
    'returns null for %s (treated as "plaintext fallback")',
    async (input) => {
      expect(await decodeInviteFragment(input as string | null)).toBeNull()
    },
  )

  it('returns null when k is present but s is missing', async () => {
    const keys = await generateFragmentKeys()
    const frag = await encodeInviteFragment(keys)
    const justK = frag.split('&')[0]
    expect(await decodeInviteFragment(justK)).toBeNull()
  })

  it('returns null on garbage master key — does not throw', async () => {
    // Well-formed param shape but the key itself fails Web Crypto import.
    const result = await decodeInviteFragment(
      'k=not-base64!!&s=AAAAAAAAAAAAAAAAAAAAAA',
    )
    expect(result).toBeNull()
  })
})
