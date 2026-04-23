import { describe, expect, it } from 'vitest'

import { hasBillingPermission } from './customerPortal'

/** ``hasBillingPermission`` is the sole pure export of
 *  ``customerPortal.ts`` — the rest require Next navigation + API
 *  client mocking. Gating billing UI to owners + billing managers, so
 *  every accept/reject case is worth pinning. */

type User = Parameters<typeof hasBillingPermission>[0]

function member(role: string): User {
  return { type: 'member', role } as unknown as NonNullable<User>
}

function customer(): User {
  return { type: 'customer' } as unknown as NonNullable<User>
}

describe('hasBillingPermission', () => {
  it('returns false when the user is undefined (unauthenticated)', () => {
    expect(hasBillingPermission(undefined)).toBe(false)
  })

  it('returns true for any customer-type user regardless of role', () => {
    // Customers (storefront buyers) always see billing for their own
    // purchases — no role gate.
    expect(hasBillingPermission(customer())).toBe(true)
  })

  it('returns true for a member with role "owner"', () => {
    expect(hasBillingPermission(member('owner'))).toBe(true)
  })

  it('returns true for a member with role "billing_manager"', () => {
    expect(hasBillingPermission(member('billing_manager'))).toBe(true)
  })

  it('returns false for a member with role "admin" (not on billing allowlist)', () => {
    expect(hasBillingPermission(member('admin'))).toBe(false)
  })

  it('returns false for a member with role "viewer"', () => {
    expect(hasBillingPermission(member('viewer'))).toBe(false)
  })

  it('returns false for a member with no role', () => {
    expect(hasBillingPermission(member(''))).toBe(false)
    expect(hasBillingPermission(member(undefined as unknown as string))).toBe(
      false,
    )
  })

  it('is case-sensitive on role (typo-safe)', () => {
    // A typo like "Owner" should fail closed — permission checks should
    // never pass by accident.
    expect(hasBillingPermission(member('Owner'))).toBe(false)
    expect(hasBillingPermission(member('OWNER'))).toBe(false)
    expect(hasBillingPermission(member('BILLING_MANAGER'))).toBe(false)
  })
})
