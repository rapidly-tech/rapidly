/** TanStack Query key factory for customer portal queries. */
export const customerPortalKeys = {
  all: ['customer-portal'],
  customer: () => [...customerPortalKeys.all, 'customer'],
}
