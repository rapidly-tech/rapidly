/**
 * HKDF sub-key derivation for P2P chambers.
 *
 * Callers provide a master key + an ``info`` string that encodes the
 * purpose (chamber + version + role). The returned CryptoKey is an
 * AES-GCM key scoped to that purpose — using the same master across
 * chambers is then safe because the ``info`` binding ensures two
 * chambers never end up sharing a derived key by coincidence.
 *
 * See ``specs/collab-e2ee.md`` §3 for the specific ``info`` strings
 * Collab will use (``collab:sync:v1`` etc).
 */

/** Convert an AES-GCM master key (which is extractable for
 *  distribution via URL fragment) into an HKDF key handle suitable
 *  for ``deriveSubKey``. Re-imports the raw material because Web
 *  Crypto's AES-GCM handles are not valid HKDF handles. */
async function asHkdfKey(masterKey: CryptoKey): Promise<CryptoKey> {
  if (masterKey.algorithm.name === 'HKDF') return masterKey
  const raw = await crypto.subtle.exportKey('raw', masterKey)
  return crypto.subtle.importKey('raw', raw, 'HKDF', false, ['deriveKey'])
}

/** Derive a purpose-scoped AES-256-GCM sub-key from a master key.
 *
 *  ``info`` must be unique per logical purpose. Salt is a fixed
 *  per-session random value so rotating sessions rotate every
 *  derived key. Callers that want key separation across sessions
 *  only (not across purposes) can pass a constant info and a random
 *  salt; callers that want both should pass distinct info AND
 *  salt. */
export async function deriveSubKey(
  masterKey: CryptoKey,
  info: Uint8Array,
  salt: Uint8Array,
): Promise<CryptoKey> {
  if (salt.byteLength === 0) {
    throw new Error('Empty salt is not allowed — weakens derived key')
  }
  const hkdfKey = await asHkdfKey(masterKey)
  return crypto.subtle.deriveKey(
    {
      name: 'HKDF',
      hash: 'SHA-256',
      salt: salt as BufferSource,
      info: info as BufferSource,
    },
    hkdfKey,
    { name: 'AES-GCM', length: 256 },
    // Non-extractable: callers never need to hand a sub-key out; only
    // the master leaves the browser (in the URL fragment).
    false,
    ['encrypt', 'decrypt'],
  )
}

export function infoFor(
  chamber: string,
  purpose: string,
  version = 'v1',
): Uint8Array {
  return new TextEncoder().encode(`${chamber}:${purpose}:${version}`)
}
