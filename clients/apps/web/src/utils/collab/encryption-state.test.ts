import { describe, expect, it } from 'vitest'

import { aggregateEncryptionState, type PeerStatus } from './encryption-state'

describe('aggregateEncryptionState', () => {
  it('returns "solo" when there are no peers', () => {
    expect(aggregateEncryptionState([])).toBe('solo')
  })

  it('returns "pending" when every peer is still pending', () => {
    expect(aggregateEncryptionState(['pending', 'pending'])).toBe('pending')
  })

  it('returns "e2ee" when every settled peer is e2ee', () => {
    expect(aggregateEncryptionState(['e2ee', 'e2ee'])).toBe('e2ee')
  })

  it('returns "plaintext" when every settled peer is plaintext', () => {
    expect(aggregateEncryptionState(['plaintext', 'plaintext'])).toBe(
      'plaintext',
    )
  })

  it('returns "mixed" when at least one peer is e2ee and one is plaintext', () => {
    expect(aggregateEncryptionState(['e2ee', 'plaintext'])).toBe('mixed')
    expect(aggregateEncryptionState(['e2ee', 'plaintext', 'pending'])).toBe(
      'mixed',
    )
  })

  it.each<[PeerStatus[], 'e2ee' | 'plaintext' | 'pending']>([
    [['e2ee', 'pending'], 'e2ee'],
    [['plaintext', 'pending'], 'plaintext'],
  ])(
    'treats pending as "not yet known" — %o resolves to %s',
    (peers, expected) => {
      expect(aggregateEncryptionState(peers)).toBe(expected)
    },
  )
})
