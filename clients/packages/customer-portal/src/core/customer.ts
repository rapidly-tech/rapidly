import type { PortalClient } from './client'
import type {
  CustomerPortalCustomer,
  CustomerPortalCustomerUpdate,
} from './types'

/** Creates methods for reading and updating the authenticated customer profile. */
export function createCustomerMethods(portalClient: PortalClient) {
  return {
    getCustomer: async (): Promise<CustomerPortalCustomer> => {
      return portalClient.request((client) =>
        client.GET('/api/customer-portal/customers/me'),
      )
    },

    updateCustomer: async (
      data: CustomerPortalCustomerUpdate,
    ): Promise<CustomerPortalCustomer> => {
      return portalClient.request((client) =>
        client.PATCH('/api/customer-portal/customers/me', {
          body: data,
        }),
      )
    },
  }
}
