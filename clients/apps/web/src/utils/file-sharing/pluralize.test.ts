import { describe, expect, it } from 'vitest'

import { pluralize } from './pluralize'

describe('pluralize', () => {
  it('uses the singular form when count is 1', () => {
    expect(pluralize(1, 'file', 'files')).toBe('1 file')
  })

  it('uses the plural form when count is 0', () => {
    expect(pluralize(0, 'file', 'files')).toBe('0 files')
  })

  it('uses the plural form when count is > 1', () => {
    expect(pluralize(2, 'file', 'files')).toBe('2 files')
    expect(pluralize(42, 'peer', 'peers')).toBe('42 peers')
  })

  it('pluralizes negative counts (unusual but not singular)', () => {
    expect(pluralize(-1, 'byte', 'bytes')).toBe('-1 bytes')
  })

  it('handles irregular plurals when passed explicitly', () => {
    expect(pluralize(1, 'child', 'children')).toBe('1 child')
    expect(pluralize(3, 'child', 'children')).toBe('3 children')
  })
})
