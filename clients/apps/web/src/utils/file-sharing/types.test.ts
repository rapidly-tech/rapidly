import { describe, expect, it } from 'vitest'

import { UploaderConnectionStatus } from './types'

/** The enum values are used as string keys in wire messages + presence
 *  payloads + UI switch statements. Pinning them prevents silent drift
 *  when someone refactors the enum declaration. */
describe('UploaderConnectionStatus', () => {
  it('exposes the expected named values', () => {
    expect(UploaderConnectionStatus.Pending).toBe('PENDING')
    expect(UploaderConnectionStatus.Ready).toBe('READY')
    expect(UploaderConnectionStatus.Paused).toBe('PAUSED')
    expect(UploaderConnectionStatus.Uploading).toBe('UPLOADING')
    expect(UploaderConnectionStatus.Done).toBe('DONE')
    expect(UploaderConnectionStatus.Authenticating).toBe('AUTHENTICATING')
    expect(UploaderConnectionStatus.InvalidPassword).toBe('INVALID_PASSWORD')
    expect(UploaderConnectionStatus.LockedOut).toBe('LOCKED_OUT')
    expect(UploaderConnectionStatus.Closed).toBe('CLOSED')
  })

  it('contains exactly the 9 documented states', () => {
    // Filter out the numeric reverse-mapping that string enums don't have,
    // just in case.
    const stringValues = Object.values(UploaderConnectionStatus).filter(
      (v) => typeof v === 'string',
    )
    expect(stringValues.sort()).toEqual(
      [
        'AUTHENTICATING',
        'CLOSED',
        'DONE',
        'INVALID_PASSWORD',
        'LOCKED_OUT',
        'PAUSED',
        'PENDING',
        'READY',
        'UPLOADING',
      ].sort(),
    )
  })

  it('uses SCREAMING_SNAKE_CASE (wire-format convention)', () => {
    for (const v of Object.values(UploaderConnectionStatus)) {
      if (typeof v !== 'string') continue
      expect(v).toMatch(/^[A-Z][A-Z_]*[A-Z]$/)
    }
  })
})
