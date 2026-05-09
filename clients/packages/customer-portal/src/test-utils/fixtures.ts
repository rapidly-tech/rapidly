import type { schemas } from '@rapidly-tech/client'

export type CustomerPortalWorkspace = schemas['CustomerWorkspace']

export type CustomerPortalProduct = schemas['CustomerProduct']

export const workspaceFixture = (
  overrides: Partial<CustomerPortalWorkspace> = {},
): CustomerPortalWorkspace =>
  ({
    id: 'org_test123',
    created_at: '2024-01-01T00:00:00Z',
    modified_at: null,
    name: 'Test Workspace',
    slug: 'test-org',
    avatar_url: null,
    customer_portal_settings: {
      usage: { show: true },
    },
    ...overrides,
  }) satisfies CustomerPortalWorkspace as CustomerPortalWorkspace

export const productFixture = (
  overrides: Partial<CustomerPortalProduct> = {},
): CustomerPortalProduct =>
  ({
    id: 'product-abc123',
    created_at: '2024-01-01T00:00:00Z',
    modified_at: null,
    name: 'Test Product',
    description: null,
    workspace_id: 'org_test123',
    visibility: 'public',
    is_archived: false,
    prices: [],
    medias: [],
    ...overrides,
  }) satisfies CustomerPortalProduct as CustomerPortalProduct

export const customerFixture = (
  overrides: Partial<schemas['CustomerPortalCustomer']> = {},
): schemas['CustomerPortalCustomer'] => ({
  id: 'customer-abc123',
  created_at: '2024-01-01T00:00:00Z',
  modified_at: null,
  email: 'test@example.com',
  email_verified: true,
  name: 'Test Customer',
  billing_name: null,
  billing_address: null,
  oauth_accounts: {},
  ...overrides,
})
