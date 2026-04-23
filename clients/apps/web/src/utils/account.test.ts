import { describe, expect, it } from 'vitest'

import { ACCOUNT_TYPE_DISPLAY_NAMES, ACCOUNT_TYPE_ICON } from './account'

describe('ACCOUNT_TYPE_DISPLAY_NAMES', () => {
  it('labels stripe as "Stripe"', () => {
    expect(ACCOUNT_TYPE_DISPLAY_NAMES.stripe).toBe('Stripe')
  })

  it('labels manual as "Manual"', () => {
    expect(ACCOUNT_TYPE_DISPLAY_NAMES.manual).toBe('Manual')
  })

  it('exposes exactly the two documented account types', () => {
    expect(Object.keys(ACCOUNT_TYPE_DISPLAY_NAMES).sort()).toEqual([
      'manual',
      'stripe',
    ])
  })
})

describe('ACCOUNT_TYPE_ICON', () => {
  it('maps each account type to a component function', () => {
    expect(typeof ACCOUNT_TYPE_ICON.stripe).toBe('function')
    expect(typeof ACCOUNT_TYPE_ICON.manual).toBe('function')
  })

  it('covers the same keys as ACCOUNT_TYPE_DISPLAY_NAMES', () => {
    expect(Object.keys(ACCOUNT_TYPE_ICON).sort()).toEqual(
      Object.keys(ACCOUNT_TYPE_DISPLAY_NAMES).sort(),
    )
  })

  it('returns distinct component functions per account type', () => {
    expect(ACCOUNT_TYPE_ICON.stripe).not.toBe(ACCOUNT_TYPE_ICON.manual)
  })
})
