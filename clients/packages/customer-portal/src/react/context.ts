import { createContext, useContext } from 'react'
import type { PortalClient } from '../core/client'

export interface CustomerPortalContextValue {
  client: PortalClient
  workspaceId: string
  workspaceSlug: string
}

export const CustomerPortalContext =
  createContext<CustomerPortalContextValue | null>(null)

/** Returns the portal client and workspace context, or throws if used outside the provider. */
export function useCustomerPortalContext(): CustomerPortalContextValue {
  const context = useContext(CustomerPortalContext)
  if (!context) {
    throw new Error(
      'useCustomerPortalContext must be used within a CustomerPortalProvider',
    )
  }
  return context
}
