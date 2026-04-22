import { describe, expect, it } from 'vitest'

import { isWhiteboardV2EnabledFromEnv } from './whiteboard-v2-flag'

describe('isWhiteboardV2EnabledFromEnv', () => {
  it('treats undefined as off', () => {
    expect(isWhiteboardV2EnabledFromEnv(undefined)).toBe(false)
  })

  it('treats empty / whitespace as off', () => {
    expect(isWhiteboardV2EnabledFromEnv('')).toBe(false)
    expect(isWhiteboardV2EnabledFromEnv('   ')).toBe(false)
  })

  it('accepts canonical truthy strings (case-insensitive)', () => {
    expect(isWhiteboardV2EnabledFromEnv('true')).toBe(true)
    expect(isWhiteboardV2EnabledFromEnv('TRUE')).toBe(true)
    expect(isWhiteboardV2EnabledFromEnv('True')).toBe(true)
    expect(isWhiteboardV2EnabledFromEnv('1')).toBe(true)
    expect(isWhiteboardV2EnabledFromEnv('on')).toBe(true)
    expect(isWhiteboardV2EnabledFromEnv(' on ')).toBe(true)
  })

  it('treats other strings as off (no ambiguous positives)', () => {
    expect(isWhiteboardV2EnabledFromEnv('false')).toBe(false)
    expect(isWhiteboardV2EnabledFromEnv('0')).toBe(false)
    expect(isWhiteboardV2EnabledFromEnv('off')).toBe(false)
    expect(isWhiteboardV2EnabledFromEnv('yes')).toBe(false)
    expect(isWhiteboardV2EnabledFromEnv('2')).toBe(false)
  })

  it('treats non-string input as off', () => {
    // Guards the edge where webpack substitutes something unexpected.
    expect(isWhiteboardV2EnabledFromEnv(42 as unknown as string)).toBe(false)
    expect(isWhiteboardV2EnabledFromEnv(null as unknown as string)).toBe(false)
  })
})
