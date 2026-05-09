import { describe, expect, it } from 'vitest'
import { InfoMessage, MessageType } from './messages'

describe('InfoMessage commitment field', () => {
  it('accepts valid 64-char hex commitment', () => {
    const msg = {
      type: MessageType.Info,
      files: [
        {
          fileName: 'test.txt',
          size: 100,
          type: 'text/plain',
          commitment: 'a'.repeat(64),
        },
      ],
    }
    const parsed = InfoMessage.parse(msg)
    expect(parsed.files[0].commitment).toBe('a'.repeat(64))
  })

  it('accepts message without commitment (backwards compat)', () => {
    const msg = {
      type: MessageType.Info,
      files: [
        {
          fileName: 'test.txt',
          size: 100,
          type: 'text/plain',
        },
      ],
    }
    const parsed = InfoMessage.parse(msg)
    expect(parsed.files[0].commitment).toBeUndefined()
  })

  it('rejects commitment with wrong length', () => {
    const msg = {
      type: MessageType.Info,
      files: [
        {
          fileName: 'test.txt',
          size: 100,
          type: 'text/plain',
          commitment: 'abc123',
        },
      ],
    }
    expect(() => InfoMessage.parse(msg)).toThrow()
  })

  it('rejects commitment with uppercase hex', () => {
    const msg = {
      type: MessageType.Info,
      files: [
        {
          fileName: 'test.txt',
          size: 100,
          type: 'text/plain',
          commitment: 'A'.repeat(64),
        },
      ],
    }
    expect(() => InfoMessage.parse(msg)).toThrow()
  })

  it('rejects commitment with non-hex characters', () => {
    const msg = {
      type: MessageType.Info,
      files: [
        {
          fileName: 'test.txt',
          size: 100,
          type: 'text/plain',
          commitment: 'g'.repeat(64),
        },
      ],
    }
    expect(() => InfoMessage.parse(msg)).toThrow()
  })
})
