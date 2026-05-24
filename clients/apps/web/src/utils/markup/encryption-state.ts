/**
 * Aggregate the per-peer encryption state into a single room-level
 * label that UI can render.
 *
 *   - ``e2ee``       — at least one peer AND every settled peer is e2ee.
 *   - ``mixed``      — some peers e2ee, some plaintext. Typical only
 *                      during the brief handshake window or if E2EE
 *                      was flipped off mid-session; surfaces in UI as
 *                      a warning colour.
 *   - ``plaintext``  — at least one peer AND every settled peer is
 *                      plaintext.
 *   - ``pending``    — there are peers but none have settled yet (the
 *                      handshake is still in flight).
 *   - ``solo``       — no peers. Self-only: "waiting for someone to
 *                      join". Intentional distinct state from
 *                      ``pending`` so the badge can read naturally.
 */
export type RoomEncryptionState =
  | 'e2ee'
  | 'mixed'
  | 'plaintext'
  | 'pending'
  | 'solo'

export type PeerStatus = 'pending' | 'e2ee' | 'plaintext'

export function aggregateEncryptionState(
  peerStatuses: readonly PeerStatus[],
): RoomEncryptionState {
  if (peerStatuses.length === 0) return 'solo'
  let hasE2ee = false
  let hasPlaintext = false
  for (const s of peerStatuses) {
    if (s === 'e2ee') hasE2ee = true
    else if (s === 'plaintext') hasPlaintext = true
  }
  if (hasE2ee && hasPlaintext) return 'mixed'
  if (hasE2ee) return 'e2ee'
  if (hasPlaintext) return 'plaintext'
  return 'pending' // only pending entries
}
