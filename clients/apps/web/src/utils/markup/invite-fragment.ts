/**
 * Invite URL fragment helpers for Collab E2EE (v1.1 PR C).
 *
 * The master key + salt ride in the URL **fragment** (``#k=...&s=...``).
 * The fragment is not transmitted to the server in the HTTP request,
 * so the Rapidly backend never sees either value. Same pattern as the
 * file-sharing chamber.
 *
 * See ``specs/collab-e2ee.md`` §"Design" §1.
 */

import {
  exportMasterKey,
  exportSalt,
  generateMasterKey,
  generateSalt,
  importMasterKey,
  importSalt,
} from '@/utils/crypto/master-key'

export interface CollabFragmentKeys {
  masterKey: CryptoKey
  salt: Uint8Array
}

/** Build the ``#k=<master>&s=<salt>`` string for an invite URL. */
export async function encodeInviteFragment(
  keys: CollabFragmentKeys,
): Promise<string> {
  const k = await exportMasterKey(keys.masterKey)
  const s = exportSalt(keys.salt)
  return `k=${k}&s=${s}`
}

/** Parse a fragment (``#...`` or ``...``) and import the master key.
 *  Returns ``null`` when the fragment is absent or malformed — the
 *  caller falls back to plaintext (v1) instead of erroring out so the
 *  chamber stays usable if someone shares a link with the fragment
 *  stripped (e.g. pasted into a markdown that ignored ``#``). */
export async function decodeInviteFragment(
  fragment: string | null | undefined,
): Promise<CollabFragmentKeys | null> {
  if (!fragment) return null
  const clean = fragment.startsWith('#') ? fragment.slice(1) : fragment
  if (clean.length === 0) return null

  const params = new URLSearchParams(clean)
  const k = params.get('k')
  const s = params.get('s')
  if (!k || !s) return null

  try {
    const masterKey = await importMasterKey(k)
    const salt = importSalt(s)
    return { masterKey, salt }
  } catch {
    // Invalid base64url, wrong length, or subtle import failure —
    // treat as "no fragment" rather than crashing the page.
    return null
  }
}

/** Generate a fresh master key + salt for a new session. */
export async function generateFragmentKeys(): Promise<CollabFragmentKeys> {
  const masterKey = await generateMasterKey()
  const salt = generateSalt()
  return { masterKey, salt }
}
