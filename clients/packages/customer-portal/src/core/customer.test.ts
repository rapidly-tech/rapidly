import { http, HttpResponse } from 'msw'
import { describe, expect, it } from 'vitest'
import { customerFixture } from '../test-utils/fixtures'
import { server } from '../test-utils/server'
import { createPortalClient } from './client'
import { createCustomerMethods } from './customer'
import { RapidlyCustomerPortalError } from './errors'

const API_BASE = 'http://example.com:8000'

describe('customer methods', () => {
  const initApiClient = () => {
    const portalClient = createPortalClient({
      token: 'test_token',
      workspaceId: 'org_123',
      baseUrl: API_BASE,
    })
    return createCustomerMethods(portalClient)
  }

  describe('getCustomer', () => {
    it('fetches the authenticated customer', async () => {
      const mockCustomer = customerFixture({ email: 'user@example.com' })

      server.use(
        http.get(`${API_BASE}/api/customer-portal/customers/me`, () => {
          return HttpResponse.json(mockCustomer)
        }),
      )

      const methods = initApiClient()
      const customer = await methods.getCustomer()

      expect(customer.id).toBe(mockCustomer.id)
      expect(customer.email).toBe('user@example.com')
    })

    it('throws RapidlyCustomerPortalError on error', async () => {
      server.use(
        http.get(`${API_BASE}/api/customer-portal/customers/me`, () => {
          return HttpResponse.json(
            { detail: 'Customer not found' },
            { status: 404 },
          )
        }),
      )

      const methods = initApiClient()

      await expect(methods.getCustomer()).rejects.toThrow(
        RapidlyCustomerPortalError,
      )
    })
  })

  describe('updateCustomer', () => {
    it('updates the customer and returns updated data', async () => {
      const updatedCustomer = customerFixture({
        billing_name: 'New Billing Name',
      })

      server.use(
        http.patch(
          `${API_BASE}/api/customer-portal/customers/me`,
          async ({ request }) => {
            const body = (await request.json()) as Record<string, unknown>
            expect(body.billing_name).toBe('New Billing Name')
            return HttpResponse.json(updatedCustomer)
          },
        ),
      )

      const methods = initApiClient()
      const result = await methods.updateCustomer({
        billing_name: 'New Billing Name',
      })

      expect(result.billing_name).toBe('New Billing Name')
    })

    it('throws RapidlyCustomerPortalError on validation error', async () => {
      server.use(
        http.patch(`${API_BASE}/api/customer-portal/customers/me`, () => {
          return HttpResponse.json(
            { detail: 'Validation error' },
            { status: 422 },
          )
        }),
      )

      const methods = initApiClient()

      await expect(
        methods.updateCustomer({ billing_name: '' }),
      ).rejects.toThrow(RapidlyCustomerPortalError)
    })
  })
})
