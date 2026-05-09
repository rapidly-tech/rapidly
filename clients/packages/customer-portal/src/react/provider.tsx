import React, { useEffect, useMemo, useRef } from 'react'
import { createPortalClient } from '../core/client'
import {
  CustomerPortalContext,
  type CustomerPortalContextValue,
} from './context'

export interface CustomerPortalProviderProps {
  token: string
  workspaceId: string
  workspaceSlug: string
  baseUrl?: string
  onUnauthorized: () => void
  children: React.ReactNode
}

/** Initialises the portal client and provides it to descendant components. */
export function CustomerPortalProvider({
  token,
  workspaceId,
  workspaceSlug,
  baseUrl,
  onUnauthorized,
  children,
}: CustomerPortalProviderProps) {
  const onUnauthorizedRef = useRef(onUnauthorized)
  useEffect(() => {
    onUnauthorizedRef.current = onUnauthorized
  }, [onUnauthorized])

  const client = useMemo(
    () =>
      createPortalClient({
        token,
        workspaceId,
        workspaceSlug,
        baseUrl,
        onUnauthorized: () => onUnauthorizedRef.current(),
      }),
    [token, workspaceId, workspaceSlug, baseUrl],
  )

  const value: CustomerPortalContextValue = useMemo(
    () => ({
      client,
      workspaceId,
      workspaceSlug,
    }),
    [client, workspaceId, workspaceSlug],
  )

  return (
    <CustomerPortalContext.Provider value={value}>
      {children}
    </CustomerPortalContext.Provider>
  )
}
