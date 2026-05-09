import { describe, expect, it } from 'vitest'

import {
  DISPLAY_NAME_MAX_LENGTH,
  DISPLAY_NAME_STORAGE_KEY,
  defaultDisplayName,
  effectiveDisplayName,
  readStoredDisplayName,
  sanitiseDisplayName,
  writeStoredDisplayName,
} from './display-name'

function fakeStorage(initial: Record<string, string> = {}) {
  const store = new Map<string, string>(Object.entries(initial))
  return {
    storage: {
      getItem: (k: string) => store.get(k) ?? null,
      setItem: (k: string, v: string) => {
        store.set(k, v)
      },
      removeItem: (k: string) => {
        store.delete(k)
      },
    },
    has: (k: string) => store.has(k),
    value: (k: string) => store.get(k),
  }
}

describe('sanitiseDisplayName', () => {
  it('returns empty string on null / undefined / non-string input', () => {
    expect(sanitiseDisplayName(null)).toBe('')
    expect(sanitiseDisplayName(undefined)).toBe('')
    expect(sanitiseDisplayName(42 as unknown as string)).toBe('')
  })

  it('trims surrounding whitespace', () => {
    expect(sanitiseDisplayName('  Alice  ')).toBe('Alice')
  })

  it('strips ASCII control characters', () => {
    expect(sanitiseDisplayName('A\u0001l\u0002i\u0003c\u007Fe')).toBe('Alice')
  })

  it('caps length at DISPLAY_NAME_MAX_LENGTH', () => {
    const oversized = 'a'.repeat(DISPLAY_NAME_MAX_LENGTH + 10)
    expect(sanitiseDisplayName(oversized).length).toBe(DISPLAY_NAME_MAX_LENGTH)
  })

  it('preserves unicode letters + emoji', () => {
    expect(sanitiseDisplayName('Ada 🦀')).toBe('Ada 🦀')
  })
})

describe('readStoredDisplayName', () => {
  it('returns empty string on SSR / missing storage', () => {
    expect(readStoredDisplayName(null)).toBe('')
  })

  it('reads the stored value + sanitises', () => {
    const { storage } = fakeStorage({
      [DISPLAY_NAME_STORAGE_KEY]: '  Alice\u0001  ',
    })
    expect(readStoredDisplayName(storage)).toBe('Alice')
  })

  it('returns empty string on missing entry', () => {
    const { storage } = fakeStorage()
    expect(readStoredDisplayName(storage)).toBe('')
  })
})

describe('writeStoredDisplayName', () => {
  it('writes sanitised value', () => {
    const { storage, value } = fakeStorage()
    writeStoredDisplayName('  Alice  ', storage)
    expect(value(DISPLAY_NAME_STORAGE_KEY)).toBe('Alice')
  })

  it('empty / whitespace input clears the entry rather than storing ""', () => {
    const { storage, has } = fakeStorage({
      [DISPLAY_NAME_STORAGE_KEY]: 'Alice',
    })
    writeStoredDisplayName('   ', storage)
    expect(has(DISPLAY_NAME_STORAGE_KEY)).toBe(false)
  })

  it('tolerates null storage (SSR)', () => {
    expect(() => writeStoredDisplayName('Alice', null)).not.toThrow()
  })

  it('swallows quota errors silently', () => {
    const storage = {
      setItem: () => {
        throw new Error('QuotaExceededError')
      },
      removeItem: () => {},
    }
    expect(() => writeStoredDisplayName('Alice', storage)).not.toThrow()
  })
})

describe('defaultDisplayName', () => {
  it('formats as "Peer <4 chars>"', () => {
    expect(defaultDisplayName(1234567890)).toBe('Peer 7890')
  })

  it('handles short clientIDs', () => {
    expect(defaultDisplayName(42)).toBe('Peer 42')
  })
})

describe('effectiveDisplayName', () => {
  it('returns typed value when non-empty', () => {
    expect(effectiveDisplayName('  Alice  ', 42)).toBe('Alice')
  })

  it('falls back to default when typed is blank', () => {
    expect(effectiveDisplayName('', 1234567890)).toBe('Peer 7890')
    expect(effectiveDisplayName('   ', 1234567890)).toBe('Peer 7890')
  })

  it('falls back to "Peer" when clientID is null', () => {
    expect(effectiveDisplayName('', null)).toBe('Peer')
  })
})
